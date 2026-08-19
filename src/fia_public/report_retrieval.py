"""Question-scoped vector retrieval with canonical PostgreSQL-style readback."""

from __future__ import annotations

import math
from dataclasses import dataclass

from .contracts import SAFE_HASH, stable_hash


class ReportRetrievalError(ValueError):
    """Raised when canonical retrieval inputs violate the public contract."""


@dataclass(frozen=True)
class CanonicalReportChunk:
    company_id: str
    document_id: str
    chunk_id: str
    source_hash: str
    lineage_hash: str
    page_number: int
    paragraph_id: str
    selected_excerpt: str
    promotion_status: str = "evidence_ready"


@dataclass(frozen=True)
class VectorHit:
    point_id: str
    company_id: str
    chunk_id: str
    lineage_hash: str
    score: float


@dataclass(frozen=True)
class QuestionScopedReportEvidence:
    evidence_id: str
    question_hash: str
    company_id: str
    document_id: str
    chunk_id: str
    source_hash: str
    page_number: int
    paragraph_id: str
    selected_excerpt: str
    score: float


@dataclass(frozen=True)
class RetrievalResult:
    status: str
    evidence: tuple[QuestionScopedReportEvidence, ...]
    rejection_reasons: tuple[str, ...]


def select_question_scoped_report_evidence(
    *,
    question_hash: str,
    company_id: str,
    vector_hits: tuple[VectorHit, ...],
    canonical_chunks: tuple[CanonicalReportChunk, ...],
    top_k: int = 5,
) -> RetrievalResult:
    if not SAFE_HASH.fullmatch(question_hash) or not company_id.startswith("krx:"):
        raise ReportRetrievalError("retrieval_scope_invalid")
    if not 1 <= top_k <= 20:
        raise ReportRetrievalError("retrieval_limit_invalid")
    canonical: dict[str, CanonicalReportChunk] = {}
    for chunk in canonical_chunks:
        _validate_chunk(chunk)
        if chunk.chunk_id in canonical:
            raise ReportRetrievalError("canonical_chunk_duplicate")
        canonical[chunk.chunk_id] = chunk

    selected: list[QuestionScopedReportEvidence] = []
    rejected: list[str] = []
    observed_chunks: set[str] = set()
    ordered_hits = sorted(vector_hits, key=lambda item: (-item.score, item.point_id))
    for hit in ordered_hits:
        if not math.isfinite(hit.score):
            rejected.append("vector_score_invalid")
            continue
        chunk = canonical.get(hit.chunk_id)
        if hit.company_id != company_id:
            rejected.append("cross_company_hit")
            continue
        if chunk is None:
            rejected.append("canonical_chunk_missing")
            continue
        if (
            chunk.company_id != company_id
            or chunk.lineage_hash != hit.lineage_hash
            or chunk.promotion_status != "evidence_ready"
        ):
            rejected.append("canonical_lineage_mismatch")
            continue
        if chunk.chunk_id in observed_chunks:
            rejected.append("duplicate_chunk_hit")
            continue
        observed_chunks.add(chunk.chunk_id)
        evidence_payload = {
            "question_hash": question_hash,
            "company_id": chunk.company_id,
            "document_id": chunk.document_id,
            "chunk_id": chunk.chunk_id,
            "source_hash": chunk.source_hash,
            "page_number": chunk.page_number,
            "paragraph_id": chunk.paragraph_id,
        }
        selected.append(
            QuestionScopedReportEvidence(
                evidence_id=stable_hash(evidence_payload),
                question_hash=question_hash,
                company_id=chunk.company_id,
                document_id=chunk.document_id,
                chunk_id=chunk.chunk_id,
                source_hash=chunk.source_hash,
                page_number=chunk.page_number,
                paragraph_id=chunk.paragraph_id,
                selected_excerpt=chunk.selected_excerpt,
                score=hit.score,
            )
        )
        if len(selected) == top_k:
            break
    status = "ready" if selected else "unsupported_by_selected_corpus"
    return RetrievalResult(status, tuple(selected), tuple(rejected))


def _validate_chunk(chunk: CanonicalReportChunk) -> None:
    if (
        not chunk.company_id.startswith("krx:")
        or not chunk.document_id
        or not chunk.chunk_id
        or not SAFE_HASH.fullmatch(chunk.source_hash)
        or not SAFE_HASH.fullmatch(chunk.lineage_hash)
        or chunk.page_number < 1
        or not chunk.paragraph_id
        or not chunk.selected_excerpt.strip()
    ):
        raise ReportRetrievalError("canonical_chunk_invalid")
