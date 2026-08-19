"""Canonical company resolution without a bundled private company catalog."""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable
from dataclasses import dataclass

COMPANY_ID = re.compile(r"^krx:(\d{6})$")
TICKER = re.compile(r"^\d{6}$")


class CompanyContractError(ValueError):
    """Raised when registry identity data violates the public contract."""


@dataclass(frozen=True)
class CompanyRecord:
    company_id: str
    ticker: str
    canonical_name: str
    aliases: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        matched = COMPANY_ID.fullmatch(self.company_id)
        if (
            matched is None
            or not TICKER.fullmatch(self.ticker)
            or matched.group(1) != self.ticker
            or not self.canonical_name.strip()
        ):
            raise CompanyContractError("company_identity_invalid")
        normalized = tuple(_normalize(value) for value in (self.canonical_name, *self.aliases))
        if any(not value for value in normalized) or len(normalized) != len(set(normalized)):
            raise CompanyContractError("company_alias_invalid")


@dataclass(frozen=True)
class ResolutionResult:
    status: str
    company_id: str | None = None
    candidates: tuple[str, ...] = ()
    reason_code: str | None = None


class CompanyRegistry:
    """Resolve only catalog-backed identities and return ambiguity explicitly."""

    def __init__(self, records: Iterable[CompanyRecord]) -> None:
        self._records = tuple(records)
        if not self._records:
            raise CompanyContractError("company_registry_empty")
        ids = [item.company_id for item in self._records]
        tickers = [item.ticker for item in self._records]
        if len(ids) != len(set(ids)) or len(tickers) != len(set(tickers)):
            raise CompanyContractError("company_registry_identity_duplicate")

        exact: dict[str, set[str]] = {}
        for item in self._records:
            values = (item.company_id, item.ticker, item.canonical_name, *item.aliases)
            for value in values:
                exact.setdefault(_normalize(value), set()).add(item.company_id)
        self._exact = exact

    def resolve(self, reference: str) -> ResolutionResult:
        if not isinstance(reference, str) or not reference.strip() or len(reference) > 100:
            return ResolutionResult("unavailable", reason_code="company_reference_invalid")
        matches = tuple(sorted(self._exact.get(_normalize(reference), ())))
        if len(matches) == 1:
            return ResolutionResult("resolved", company_id=matches[0])
        if len(matches) > 1:
            return ResolutionResult(
                "clarification_required",
                candidates=matches,
                reason_code="company_reference_ambiguous",
            )
        return ResolutionResult("unavailable", reason_code="company_not_identified")


def _normalize(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).casefold().strip()
    return re.sub(r"\s+", " ", normalized)
