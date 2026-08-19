from __future__ import annotations

import sys
import unittest
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fia_public.contracts import stable_hash  # noqa: E402
from fia_public.integrated_analysis import (  # noqa: E402
    AxisEvidence,
    ComparisonDescriptor,
    IntegratedAnalysisError,
    build_integrated_analysis,
)


class IntegratedAnalysisTests(unittest.TestCase):
    def setUp(self) -> None:
        self.company_id = "krx:000001"
        self.report_id = stable_hash("report-evidence")
        self.report_citation = stable_hash("report-citation")
        self.financial_id = stable_hash("financial-evidence")
        self.financial_citation = stable_hash("financial-citation")
        self.axes = (
            AxisEvidence(
                "financial",
                self.company_id,
                "ready",
                (self.financial_id,),
                (self.financial_citation,),
            ),
            AxisEvidence(
                "market",
                self.company_id,
                "unavailable",
                limitation="market_data_unavailable",
            ),
            AxisEvidence(
                "report",
                self.company_id,
                "ready",
                (self.report_id,),
                (self.report_citation,),
            ),
        )
        self.descriptors = (
            ComparisonDescriptor(
                self.company_id,
                "report",
                "forecast",
                "revenue",
                "FY2026F",
                "KRW",
                "up",
                self.report_id,
                self.report_citation,
            ),
            ComparisonDescriptor(
                self.company_id,
                "financial",
                "actual",
                "revenue",
                "FY2025",
                "KRW",
                "up",
                self.financial_id,
                self.financial_citation,
            ),
        )

    def test_partial_result_and_cross_axis_observation_are_citation_bound(self) -> None:
        result = build_integrated_analysis(
            company_id=self.company_id,
            requested_axes=("financial", "market", "report"),
            axis_evidence=self.axes,
            descriptors=self.descriptors,
        )
        self.assertEqual(result.status, "ready_partial")
        self.assertEqual(result.ready_axes, ("financial", "report"))
        self.assertEqual(len(result.observations), 1)
        self.assertEqual(result.observations[0].comparison_type, "direction_consistent")
        self.assertEqual(result.unsupported_claim_count, 0)

    def test_all_requested_axes_ready_returns_analysis_ready(self) -> None:
        market = AxisEvidence(
            "market",
            self.company_id,
            "ready",
            (stable_hash("market-evidence"),),
            (stable_hash("market-citation"),),
        )
        axes = tuple(market if item.axis == "market" else item for item in self.axes)
        result = build_integrated_analysis(
            company_id=self.company_id,
            requested_axes=("financial", "market", "report"),
            axis_evidence=axes,
            descriptors=self.descriptors,
        )
        self.assertEqual(result.status, "analysis_ready")

    def test_wrong_company_and_unbound_citation_fail_closed(self) -> None:
        wrong_company = tuple(
            replace(item, company_id="krx:000002") if item.axis == "report" else item
            for item in self.axes
        )
        with self.assertRaises(IntegratedAnalysisError):
            build_integrated_analysis(
                company_id=self.company_id,
                requested_axes=("financial", "market", "report"),
                axis_evidence=wrong_company,
            )
        bad_descriptor = replace(self.descriptors[0], citation_id=stable_hash("unbound"))
        with self.assertRaises(IntegratedAnalysisError):
            build_integrated_analysis(
                company_id=self.company_id,
                requested_axes=("financial", "market", "report"),
                axis_evidence=self.axes,
                descriptors=(bad_descriptor, self.descriptors[1]),
            )

    def test_single_ready_axis_has_no_cross_axis_observation(self) -> None:
        report_unavailable = AxisEvidence(
            "report",
            self.company_id,
            "unavailable",
            limitation="report_unavailable_no_source",
        )
        axes = tuple(report_unavailable if item.axis == "report" else item for item in self.axes)
        result = build_integrated_analysis(
            company_id=self.company_id,
            requested_axes=("financial", "market", "report"),
            axis_evidence=axes,
        )
        self.assertEqual(result.status, "ready_partial")
        self.assertEqual(result.observations, ())

    def test_descriptor_from_another_company_is_rejected(self) -> None:
        wrong_descriptor = replace(self.descriptors[0], company_id="krx:000002")
        with self.assertRaises(IntegratedAnalysisError):
            build_integrated_analysis(
                company_id=self.company_id,
                requested_axes=("financial", "market", "report"),
                axis_evidence=self.axes,
                descriptors=(wrong_descriptor, self.descriptors[1]),
            )


if __name__ == "__main__":
    unittest.main()
