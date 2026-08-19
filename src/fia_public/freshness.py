"""Deterministic report-corpus freshness classification."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

REPORT_FRESHNESS_MIN_DAYS = 7
REPORT_FRESHNESS_MAX_DAYS = 14


class FreshnessContractError(ValueError):
    """Raised when an artifact cannot be classified safely."""


@dataclass(frozen=True)
class ReportFreshnessPolicy:
    days: int = 14

    def __post_init__(self) -> None:
        if not REPORT_FRESHNESS_MIN_DAYS <= self.days <= REPORT_FRESHNESS_MAX_DAYS:
            raise FreshnessContractError("report_freshness_window_invalid")


@dataclass(frozen=True)
class ReportCorpusSnapshot:
    company_id: str
    source_contract_id: str
    last_successful_source_check: datetime | None
    latest_publication_at: datetime | None
    source_hash: str | None
    artifact_ready: bool
    lineage_valid: bool = True
    negative_cache: bool = False


@dataclass(frozen=True)
class FreshnessResult:
    status: str
    needs_acquisition: bool
    reusable: bool


DEFAULT_REPORT_FRESHNESS_POLICY = ReportFreshnessPolicy()


def classify_report_freshness(
    snapshot: ReportCorpusSnapshot | None,
    *,
    as_of: datetime,
    policy: ReportFreshnessPolicy | None = None,
) -> FreshnessResult:
    policy = policy or DEFAULT_REPORT_FRESHNESS_POLICY
    if as_of.tzinfo is None:
        raise FreshnessContractError("analysis_as_of_timezone_required")
    observed_at = as_of.astimezone(UTC)
    if snapshot is None:
        return FreshnessResult("missing_report_corpus", True, False)
    if not snapshot.company_id or not snapshot.source_contract_id:
        raise FreshnessContractError("report_cache_identity_invalid")
    if not snapshot.lineage_valid:
        return FreshnessResult("lineage_mismatch", False, False)
    if snapshot.artifact_ready and not snapshot.source_hash:
        return FreshnessResult("corrupt_private_artifact", False, False)
    checked_at = _utc(snapshot.last_successful_source_check)
    if checked_at is None:
        return FreshnessResult("stale_refresh_required", True, snapshot.artifact_ready)
    if checked_at > observed_at:
        raise FreshnessContractError("source_check_from_future")
    fresh = observed_at - checked_at <= timedelta(days=policy.days)
    if snapshot.negative_cache and fresh:
        return FreshnessResult("negative_cache_hit", False, False)
    if snapshot.artifact_ready and fresh:
        return FreshnessResult("fresh_cache_hit", False, True)
    if snapshot.artifact_ready:
        return FreshnessResult("stale_refresh_required", True, True)
    return FreshnessResult("missing_report_corpus", True, False)


def _utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        raise FreshnessContractError("source_check_timezone_required")
    return value.astimezone(UTC)
