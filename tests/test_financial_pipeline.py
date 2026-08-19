from __future__ import annotations

import sys
import unittest
from dataclasses import replace
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fia_public.contracts import stable_hash  # noqa: E402
from fia_public.financial_pipeline import (  # noqa: E402
    FinancialCandidate,
    FinancialFreshnessState,
    FinancialPipelineError,
    classify_financial_freshness,
    promote_financial_candidate,
)


class FinancialPipelineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.as_of = date(2026, 8, 19)
        self.candidate = FinancialCandidate(
            company_id="krx:000001",
            ticker="000001",
            corp_code_hash=stable_hash("sample-corp-code"),
            fiscal_year=2025,
            report_code="11011",
            fiscal_period="FY2025",
            statement_type="CFS",
            metric="revenue",
            unit="KRW",
            value="1,250.00",
            receipt_hash=stable_hash("sample-receipt"),
            filing_date=date(2026, 3, 20),
        )

    def test_candidate_preserves_accounting_lineage(self) -> None:
        evidence = promote_financial_candidate(self.candidate, analysis_as_of=self.as_of)
        self.assertEqual(evidence.company_id, "krx:000001")
        self.assertEqual(evidence.statement_type, "CFS")
        self.assertEqual(evidence.unit, "KRW")
        self.assertEqual(evidence.value, "1250")
        self.assertEqual(evidence.receipt_hash, self.candidate.receipt_hash)

    def test_equivalent_numeric_formats_have_one_evidence_identity(self) -> None:
        first = promote_financial_candidate(self.candidate, analysis_as_of=self.as_of)
        second = promote_financial_candidate(
            replace(self.candidate, value="1250"),
            analysis_as_of=self.as_of,
        )
        self.assertEqual(first.evidence_id, second.evidence_id)

    def test_company_period_scope_and_future_filing_fail_closed(self) -> None:
        invalid = (
            replace(self.candidate, company_id="krx:000002"),
            replace(self.candidate, report_code="annual"),
            replace(self.candidate, statement_type="UNKNOWN"),
            replace(self.candidate, filing_date=date(2027, 1, 1)),
        )
        for candidate in invalid:
            with self.subTest(candidate=candidate):
                with self.assertRaises(FinancialPipelineError):
                    promote_financial_candidate(candidate, analysis_as_of=self.as_of)

    def test_financial_freshness_uses_receipt_version_not_report_ttl(self) -> None:
        receipt = stable_hash("receipt-v1")
        ready = FinancialFreshnessState(True, receipt, receipt, True)
        stale = replace(ready, latest_receipt_hash=stable_hash("receipt-v2"))
        self.assertEqual(classify_financial_freshness(ready), "financial_fresh_ready")
        self.assertEqual(
            classify_financial_freshness(stale),
            "financial_filing_version_stale",
        )

    def test_missing_and_lineage_mismatch_are_distinct(self) -> None:
        self.assertEqual(classify_financial_freshness(None), "financial_missing")
        mismatch = FinancialFreshnessState(True, "invalid", stable_hash("receipt"), True)
        self.assertEqual(
            classify_financial_freshness(mismatch),
            "financial_lineage_mismatch",
        )


if __name__ == "__main__":
    unittest.main()
