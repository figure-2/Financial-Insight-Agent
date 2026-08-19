from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fia_public.company_runtime import CompanyRecord, CompanyRegistry  # noqa: E402
from fia_public.contracts import stable_hash  # noqa: E402
from fia_public.durable_runtime import DurableJobRepository  # noqa: E402
from fia_public.integrated_analysis import AxisEvidence  # noqa: E402
from fia_public.service_runtime import (  # noqa: E402
    AnalysisRequest,
    GenericAnalysisService,
    ServiceRuntimeError,
)


class ServiceRuntimeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = CompanyRegistry(
            (
                CompanyRecord("krx:000001", "000001", "샘플전자", ("공통그룹",)),
                CompanyRecord("krx:000002", "000002", "샘플모빌리티", ("공통그룹",)),
            )
        )
        self.request = AnalysisRequest(
            company_reference="샘플전자",
            question_hash=stable_hash("private-question-placeholder"),
            requested_axes=("financial", "market", "report"),
            analysis_as_of="2026-08-19",
        )

    def test_terminal_axis_evidence_returns_immediate_partial_result(self) -> None:
        evidence = (
            AxisEvidence(
                "financial",
                "krx:000001",
                "ready",
                (stable_hash("financial"),),
                (stable_hash("financial-citation"),),
            ),
            AxisEvidence(
                "market",
                "krx:000001",
                "unavailable",
                limitation="market_data_unavailable",
            ),
            AxisEvidence(
                "report",
                "krx:000001",
                "unavailable",
                limitation="report_unavailable_no_source",
            ),
        )
        service = GenericAnalysisService(
            registry=self.registry,
            jobs=DurableJobRepository(),
            evidence=evidence,
        )
        response = service.submit(self.request)
        self.assertEqual(response.http_status, 200)
        self.assertEqual(response.status, "ready_partial")
        self.assertIsNotNone(response.result)
        assert response.result is not None
        self.assertEqual(response.result.ready_axes, ("financial",))

    def test_missing_axis_creates_one_idempotent_job(self) -> None:
        service = GenericAnalysisService(
            registry=self.registry,
            jobs=DurableJobRepository(),
        )
        first = service.submit(self.request)
        second = service.submit(self.request)
        self.assertEqual(first.http_status, 202)
        self.assertEqual(first.job_id, second.job_id)
        self.assertTrue(first.job_created)
        self.assertFalse(second.job_created)

    def test_ambiguity_requires_candidate_selection(self) -> None:
        service = GenericAnalysisService(
            registry=self.registry,
            jobs=DurableJobRepository(),
        )
        ambiguous = AnalysisRequest(
            company_reference="공통그룹",
            question_hash=self.request.question_hash,
            requested_axes=self.request.requested_axes,
            analysis_as_of=self.request.analysis_as_of,
        )
        response = service.submit(ambiguous)
        self.assertEqual(response.http_status, 409)
        self.assertEqual(response.status, "clarification_required")
        resumed = service.submit(ambiguous, selected_company_id="krx:000002")
        self.assertEqual(resumed.http_status, 202)
        self.assertEqual(resumed.company_id, "krx:000002")

    def test_candidate_injection_and_unknown_company_fail_closed(self) -> None:
        service = GenericAnalysisService(
            registry=self.registry,
            jobs=DurableJobRepository(),
        )
        ambiguous = AnalysisRequest(
            company_reference="공통그룹",
            question_hash=self.request.question_hash,
            requested_axes=self.request.requested_axes,
            analysis_as_of=self.request.analysis_as_of,
        )
        with self.assertRaises(ServiceRuntimeError):
            service.submit(ambiguous, selected_company_id="krx:999999")
        unknown = AnalysisRequest(
            company_reference="없는기업",
            question_hash=self.request.question_hash,
            requested_axes=self.request.requested_axes,
            analysis_as_of=self.request.analysis_as_of,
        )
        self.assertEqual(service.submit(unknown).http_status, 404)


if __name__ == "__main__":
    unittest.main()
