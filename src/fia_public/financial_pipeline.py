"""Normalized filing evidence with period, unit, scope, and version lineage."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from datetime import date
from decimal import Decimal, InvalidOperation

from .contracts import SAFE_HASH, stable_hash

TICKER = re.compile(r"^\d{6}$")
REPORT_CODE = re.compile(r"^\d{5}$")
ALLOWED_STATEMENT_TYPES = {"CFS", "OFS"}


class FinancialPipelineError(ValueError):
    """Raised when filing evidence loses identity or accounting lineage."""


@dataclass(frozen=True)
class FinancialCandidate:
    company_id: str
    ticker: str
    corp_code_hash: str
    fiscal_year: int
    report_code: str
    fiscal_period: str
    statement_type: str
    metric: str
    unit: str
    value: str
    receipt_hash: str
    filing_date: date


@dataclass(frozen=True)
class FinancialEvidence:
    evidence_id: str
    company_id: str
    ticker: str
    fiscal_year: int
    report_code: str
    fiscal_period: str
    statement_type: str
    metric: str
    unit: str
    value: str
    receipt_hash: str
    filing_date: str


@dataclass(frozen=True)
class FinancialFreshnessState:
    artifact_ready: bool
    stored_receipt_hash: str | None
    latest_receipt_hash: str | None
    source_check_succeeded: bool


def promote_financial_candidate(
    candidate: FinancialCandidate,
    *,
    analysis_as_of: date,
) -> FinancialEvidence:
    _validate_candidate(candidate, analysis_as_of=analysis_as_of)
    canonical_value = _canonical_decimal(candidate.value)
    payload = {
        **asdict(candidate),
        "filing_date": candidate.filing_date.isoformat(),
        "value": canonical_value,
    }
    return FinancialEvidence(
        evidence_id=stable_hash(payload),
        company_id=candidate.company_id,
        ticker=candidate.ticker,
        fiscal_year=candidate.fiscal_year,
        report_code=candidate.report_code,
        fiscal_period=candidate.fiscal_period,
        statement_type=candidate.statement_type,
        metric=candidate.metric,
        unit=candidate.unit,
        value=canonical_value,
        receipt_hash=candidate.receipt_hash,
        filing_date=candidate.filing_date.isoformat(),
    )


def classify_financial_freshness(state: FinancialFreshnessState | None) -> str:
    if state is None or not state.artifact_ready:
        return "financial_missing"
    if not state.source_check_succeeded:
        return "financial_source_check_required"
    if not SAFE_HASH.fullmatch(state.stored_receipt_hash or ""):
        return "financial_lineage_mismatch"
    if not SAFE_HASH.fullmatch(state.latest_receipt_hash or ""):
        return "financial_source_version_unknown"
    if state.stored_receipt_hash != state.latest_receipt_hash:
        return "financial_filing_version_stale"
    return "financial_fresh_ready"


def _validate_candidate(candidate: FinancialCandidate, *, analysis_as_of: date) -> None:
    expected_id = f"krx:{candidate.ticker}"
    if (
        candidate.company_id != expected_id
        or not TICKER.fullmatch(candidate.ticker)
        or not SAFE_HASH.fullmatch(candidate.corp_code_hash)
        or not 2000 <= candidate.fiscal_year <= analysis_as_of.year
        or not REPORT_CODE.fullmatch(candidate.report_code)
        or not candidate.fiscal_period
        or candidate.statement_type not in ALLOWED_STATEMENT_TYPES
        or not candidate.metric
        or not candidate.unit
        or not SAFE_HASH.fullmatch(candidate.receipt_hash)
        or candidate.filing_date > analysis_as_of
    ):
        raise FinancialPipelineError("financial_candidate_invalid")
    _canonical_decimal(candidate.value)


def _canonical_decimal(value: str) -> str:
    try:
        number = Decimal(value.replace(",", ""))
    except (AttributeError, InvalidOperation) as exc:
        raise FinancialPipelineError("financial_value_invalid") from exc
    if not number.is_finite():
        raise FinancialPipelineError("financial_value_invalid")
    normalized = format(number, "f")
    if "." in normalized:
        normalized = normalized.rstrip("0").rstrip(".")
    return normalized or "0"
