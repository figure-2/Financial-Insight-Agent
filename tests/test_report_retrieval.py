from __future__ import annotations

import sys
import unittest
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fia_public.contracts import stable_hash  # noqa: E402
from fia_public.report_retrieval import (  # noqa: E402
    CanonicalReportChunk,
    VectorHit,
    select_question_scoped_report_evidence,
)


class ReportRetrievalTests(unittest.TestCase):
    def setUp(self) -> None:
        self.company_id = "krx:000001"
        self.question_hash = stable_hash("sample-question")
        self.chunk = CanonicalReportChunk(
            company_id=self.company_id,
            document_id="document-1",
            chunk_id="chunk-1",
            source_hash=stable_hash("source-1"),
            lineage_hash=stable_hash("lineage-1"),
            page_number=3,
            paragraph_id="paragraph-2",
            selected_excerpt="공개 테스트를 위한 합성 근거 문장입니다.",
        )
        self.hit = VectorHit(
            point_id="point-1",
            company_id=self.company_id,
            chunk_id=self.chunk.chunk_id,
            lineage_hash=self.chunk.lineage_hash,
            score=0.92,
        )

    def test_vector_hit_requires_canonical_readback(self) -> None:
        result = select_question_scoped_report_evidence(
            question_hash=self.question_hash,
            company_id=self.company_id,
            vector_hits=(self.hit,),
            canonical_chunks=(self.chunk,),
        )
        self.assertEqual(result.status, "ready")
        self.assertEqual(len(result.evidence), 1)
        self.assertEqual(result.evidence[0].question_hash, self.question_hash)
        self.assertEqual(result.evidence[0].page_number, 3)

    def test_cross_company_and_lineage_mismatch_are_not_selected(self) -> None:
        cross_company = replace(self.hit, company_id="krx:000002", score=1.0)
        wrong_lineage = replace(self.hit, point_id="point-2", lineage_hash=stable_hash("wrong"))
        result = select_question_scoped_report_evidence(
            question_hash=self.question_hash,
            company_id=self.company_id,
            vector_hits=(cross_company, wrong_lineage),
            canonical_chunks=(self.chunk,),
        )
        self.assertEqual(result.status, "unsupported_by_selected_corpus")
        self.assertEqual(result.evidence, ())
        self.assertEqual(
            result.rejection_reasons,
            ("cross_company_hit", "canonical_lineage_mismatch"),
        )

    def test_no_promote_chunk_is_excluded(self) -> None:
        blocked = replace(self.chunk, promotion_status="reconciliation_required")
        result = select_question_scoped_report_evidence(
            question_hash=self.question_hash,
            company_id=self.company_id,
            vector_hits=(self.hit,),
            canonical_chunks=(blocked,),
        )
        self.assertFalse(result.evidence)
        self.assertIn("canonical_lineage_mismatch", result.rejection_reasons)

    def test_duplicate_vector_hits_produce_one_evidence(self) -> None:
        duplicate = replace(self.hit, point_id="point-2", score=0.91)
        result = select_question_scoped_report_evidence(
            question_hash=self.question_hash,
            company_id=self.company_id,
            vector_hits=(self.hit, duplicate),
            canonical_chunks=(self.chunk,),
        )
        self.assertEqual(len(result.evidence), 1)
        self.assertIn("duplicate_chunk_hit", result.rejection_reasons)


if __name__ == "__main__":
    unittest.main()
