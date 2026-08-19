from __future__ import annotations

import sys
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fia_public.company_runtime import CompanyRecord, CompanyRegistry  # noqa: E402
from fia_public.freshness import (  # noqa: E402
    FreshnessContractError,
    ReportCorpusSnapshot,
    ReportFreshnessPolicy,
    classify_report_freshness,
)


class CompanyRuntimeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = CompanyRegistry(
            (
                CompanyRecord("krx:000001", "000001", "샘플전자", ("sample", "공통그룹")),
                CompanyRecord(
                    "krx:000002",
                    "000002",
                    "샘플모빌리티",
                    ("sample mobility", "공통그룹"),
                ),
            )
        )

    def test_exact_name_ticker_and_alias_resolve_to_same_company(self) -> None:
        references = ("샘플전자", "000001", "krx:000001", " SAMPLE ")
        self.assertEqual(
            {self.registry.resolve(reference).company_id for reference in references},
            {"krx:000001"},
        )

    def test_ambiguous_alias_requires_clarification(self) -> None:
        result = self.registry.resolve("공통그룹")
        self.assertEqual(result.status, "clarification_required")
        self.assertEqual(result.candidates, ("krx:000001", "krx:000002"))

    def test_unknown_company_does_not_fall_back(self) -> None:
        result = self.registry.resolve("없는기업")
        self.assertEqual(result.status, "unavailable")
        self.assertEqual(result.reason_code, "company_not_identified")


class ReportFreshnessTests(unittest.TestCase):
    def setUp(self) -> None:
        self.as_of = datetime(2026, 8, 19, 12, tzinfo=UTC)

    def _snapshot(self, checked_days_ago: int, **overrides: object) -> ReportCorpusSnapshot:
        values = {
            "company_id": "krx:000001",
            "source_contract_id": "public-sample-source.v1",
            "last_successful_source_check": self.as_of - timedelta(days=checked_days_ago),
            "latest_publication_at": self.as_of - timedelta(days=20),
            "source_hash": "sha256:" + "a" * 64,
            "artifact_ready": True,
        }
        values.update(overrides)
        return ReportCorpusSnapshot(**values)

    def test_14_day_boundary_is_fresh_and_15_is_stale(self) -> None:
        self.assertEqual(
            classify_report_freshness(self._snapshot(14), as_of=self.as_of).status,
            "fresh_cache_hit",
        )
        stale = classify_report_freshness(self._snapshot(15), as_of=self.as_of)
        self.assertEqual(stale.status, "stale_refresh_required")
        self.assertTrue(stale.reusable)

    def test_fresh_negative_cache_prevents_provider_work(self) -> None:
        result = classify_report_freshness(
            self._snapshot(3, artifact_ready=False, source_hash=None, negative_cache=True),
            as_of=self.as_of,
        )
        self.assertEqual(result.status, "negative_cache_hit")
        self.assertFalse(result.needs_acquisition)

    def test_missing_and_lineage_failure_are_distinct(self) -> None:
        self.assertEqual(
            classify_report_freshness(None, as_of=self.as_of).status,
            "missing_report_corpus",
        )
        self.assertEqual(
            classify_report_freshness(
                self._snapshot(1, lineage_valid=False), as_of=self.as_of
            ).status,
            "lineage_mismatch",
        )

    def test_policy_and_timezone_fail_closed(self) -> None:
        with self.assertRaises(FreshnessContractError):
            ReportFreshnessPolicy(days=15)
        with self.assertRaises(FreshnessContractError):
            classify_report_freshness(self._snapshot(1), as_of=datetime(2026, 8, 19))


if __name__ == "__main__":
    unittest.main()
