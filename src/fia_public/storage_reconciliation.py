"""Pure reconciliation contract for canonical chunks and vector projections."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TypeVar

from .contracts import SAFE_HASH

T = TypeVar("T")


class StorageReconciliationError(ValueError):
    """Raised when persistence metadata is malformed or duplicated."""


@dataclass(frozen=True)
class CanonicalProjection:
    chunk_id: str
    company_id: str
    source_hash: str
    lineage_hash: str
    active_reference_count: int
    recoverable_vector_hash: str | None = None


@dataclass(frozen=True)
class VectorProjection:
    point_id: str
    chunk_id: str
    company_id: str
    source_hash: str
    lineage_hash: str
    vector_hash: str


@dataclass(frozen=True)
class ProjectionDecision:
    chunk_id: str
    classification: str
    evidence_ready: bool


@dataclass(frozen=True)
class ReconciliationResult:
    status: str
    decisions: tuple[ProjectionDecision, ...]
    orphan_point_ids: tuple[str, ...]


def reconcile_projections(
    *,
    canonical_rows: tuple[CanonicalProjection, ...],
    vector_points: tuple[VectorProjection, ...],
) -> ReconciliationResult:
    canonical = _unique_by(canonical_rows, lambda item: item.chunk_id, "canonical_chunk_duplicate")
    vectors = _unique_by(vector_points, lambda item: item.chunk_id, "vector_chunk_duplicate")
    point_ids = [item.point_id for item in vector_points]
    if len(point_ids) != len(set(point_ids)):
        raise StorageReconciliationError("vector_point_duplicate")

    decisions: list[ProjectionDecision] = []
    for chunk_id in sorted(canonical):
        row = canonical[chunk_id]
        _validate_canonical(row)
        point = vectors.get(chunk_id)
        if point is None:
            if row.active_reference_count > 0 and row.recoverable_vector_hash:
                classification = "active_rebuildable_without_reembedding"
            elif row.active_reference_count > 0:
                classification = "active_recovery_blocked"
            elif row.recoverable_vector_hash:
                classification = "legacy_unreferenced_rebuildable"
            else:
                classification = "legacy_unrecoverable_preserved"
            decisions.append(ProjectionDecision(chunk_id, classification, False))
            continue
        _validate_vector(point)
        identity_matches = (
            point.company_id == row.company_id
            and point.source_hash == row.source_hash
            and point.lineage_hash == row.lineage_hash
            and (
                row.recoverable_vector_hash is None
                or row.recoverable_vector_hash == point.vector_hash
            )
        )
        if not identity_matches:
            decisions.append(ProjectionDecision(chunk_id, "projection_lineage_invalid", False))
        elif row.active_reference_count > 0:
            decisions.append(ProjectionDecision(chunk_id, "active_projection_ready", True))
        else:
            decisions.append(ProjectionDecision(chunk_id, "legacy_projection_ready", False))

    orphan_ids = tuple(
        sorted(point.point_id for chunk_id, point in vectors.items() if chunk_id not in canonical)
    )
    classifications = {item.classification for item in decisions}
    if "projection_lineage_invalid" in classifications or orphan_ids:
        status = "failed_lineage_mismatch"
    elif "active_recovery_blocked" in classifications:
        status = "active_projection_recovery_blocked"
    elif "active_rebuildable_without_reembedding" in classifications:
        status = "active_projection_recovery_required"
    elif "legacy_unrecoverable_preserved" in classifications:
        status = "active_ready_with_legacy_quarantined"
    else:
        status = "active_projection_ready"
    return ReconciliationResult(status, tuple(decisions), orphan_ids)


def _unique_by(items: tuple[T, ...], key: Callable[[T], str], reason: str) -> dict[str, T]:
    values: dict[str, T] = {}
    for item in items:
        item_key = key(item)
        if item_key in values:
            raise StorageReconciliationError(reason)
        values[item_key] = item
    return values


def _validate_canonical(row: CanonicalProjection) -> None:
    if (
        not row.chunk_id
        or not row.company_id.startswith("krx:")
        or not SAFE_HASH.fullmatch(row.source_hash)
        or not SAFE_HASH.fullmatch(row.lineage_hash)
        or row.active_reference_count < 0
        or (
            row.recoverable_vector_hash is not None
            and not SAFE_HASH.fullmatch(row.recoverable_vector_hash)
        )
    ):
        raise StorageReconciliationError("canonical_projection_invalid")


def _validate_vector(point: VectorProjection) -> None:
    if (
        not point.point_id
        or not point.chunk_id
        or not point.company_id.startswith("krx:")
        or not SAFE_HASH.fullmatch(point.source_hash)
        or not SAFE_HASH.fullmatch(point.lineage_hash)
        or not SAFE_HASH.fullmatch(point.vector_hash)
    ):
        raise StorageReconciliationError("vector_projection_invalid")
