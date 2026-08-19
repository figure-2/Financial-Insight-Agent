from __future__ import annotations

import sys
import unittest
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fia_public.contracts import stable_hash  # noqa: E402
from fia_public.storage_reconciliation import (  # noqa: E402
    CanonicalProjection,
    VectorProjection,
    reconcile_projections,
)


class StorageReconciliationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.canonical = CanonicalProjection(
            chunk_id="chunk-1",
            company_id="krx:000001",
            source_hash=stable_hash("source"),
            lineage_hash=stable_hash("lineage"),
            active_reference_count=1,
            recoverable_vector_hash=stable_hash("vector"),
        )
        self.point = VectorProjection(
            point_id="point-1",
            chunk_id="chunk-1",
            company_id="krx:000001",
            source_hash=self.canonical.source_hash,
            lineage_hash=self.canonical.lineage_hash,
            vector_hash=self.canonical.recoverable_vector_hash or "",
        )

    def test_exact_active_projection_is_ready(self) -> None:
        result = reconcile_projections(
            canonical_rows=(self.canonical,),
            vector_points=(self.point,),
        )
        self.assertEqual(result.status, "active_projection_ready")
        self.assertTrue(result.decisions[0].evidence_ready)

    def test_active_missing_projection_has_explicit_recovery_states(self) -> None:
        rebuildable = reconcile_projections(
            canonical_rows=(self.canonical,),
            vector_points=(),
        )
        blocked = reconcile_projections(
            canonical_rows=(replace(self.canonical, recoverable_vector_hash=None),),
            vector_points=(),
        )
        self.assertEqual(rebuildable.status, "active_projection_recovery_required")
        self.assertEqual(blocked.status, "active_projection_recovery_blocked")
        self.assertFalse(blocked.decisions[0].evidence_ready)

    def test_unreferenced_unrecoverable_legacy_is_quarantined_not_deleted(self) -> None:
        legacy = replace(
            self.canonical,
            active_reference_count=0,
            recoverable_vector_hash=None,
        )
        result = reconcile_projections(canonical_rows=(legacy,), vector_points=())
        self.assertEqual(result.status, "active_ready_with_legacy_quarantined")
        self.assertEqual(
            result.decisions[0].classification,
            "legacy_unrecoverable_preserved",
        )
        self.assertFalse(result.decisions[0].evidence_ready)

    def test_orphan_and_payload_tamper_fail_closed(self) -> None:
        orphan = replace(self.point, point_id="orphan", chunk_id="missing")
        orphan_result = reconcile_projections(canonical_rows=(), vector_points=(orphan,))
        self.assertEqual(orphan_result.status, "failed_lineage_mismatch")
        self.assertEqual(orphan_result.orphan_point_ids, ("orphan",))

        tampered = replace(self.point, lineage_hash=stable_hash("tampered"))
        tampered_result = reconcile_projections(
            canonical_rows=(self.canonical,),
            vector_points=(tampered,),
        )
        self.assertEqual(tampered_result.status, "failed_lineage_mismatch")
        self.assertFalse(tampered_result.decisions[0].evidence_ready)

    def test_reconciliation_is_deterministic(self) -> None:
        first = reconcile_projections(
            canonical_rows=(self.canonical,),
            vector_points=(self.point,),
        )
        second = reconcile_projections(
            canonical_rows=(self.canonical,),
            vector_points=(self.point,),
        )
        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
