"""Citation-bound capability assembly and cross-axis observations."""

from __future__ import annotations

from dataclasses import dataclass

from .contracts import SAFE_HASH, stable_hash

ANALYSIS_AXES = ("financial", "market", "report")
READY_STATUS = "ready"


class IntegratedAnalysisError(ValueError):
    """Raised when evidence crosses company, source-role, or citation boundaries."""


@dataclass(frozen=True)
class AxisEvidence:
    axis: str
    company_id: str
    status: str
    evidence_ids: tuple[str, ...] = ()
    citation_ids: tuple[str, ...] = ()
    limitation: str | None = None


@dataclass(frozen=True)
class ComparisonDescriptor:
    company_id: str
    axis: str
    source_role: str
    metric: str
    period: str
    unit: str
    direction: str
    evidence_id: str
    citation_id: str


@dataclass(frozen=True)
class CrossAxisObservation:
    observation_id: str
    company_id: str
    comparison_type: str
    metric: str
    report_period: str
    financial_period: str
    unit: str
    report_evidence_id: str
    financial_evidence_id: str
    report_citation_id: str
    financial_citation_id: str
    limitation: str


@dataclass(frozen=True)
class IntegratedAnalysis:
    status: str
    company_id: str
    requested_axes: tuple[str, ...]
    ready_axes: tuple[str, ...]
    unavailable_axes: tuple[str, ...]
    observations: tuple[CrossAxisObservation, ...]
    unsupported_claim_count: int = 0


def build_integrated_analysis(
    *,
    company_id: str,
    requested_axes: tuple[str, ...],
    axis_evidence: tuple[AxisEvidence, ...],
    descriptors: tuple[ComparisonDescriptor, ...] = (),
) -> IntegratedAnalysis:
    if (
        not company_id.startswith("krx:")
        or tuple(sorted(set(requested_axes))) != requested_axes
        or not requested_axes
        or any(axis not in ANALYSIS_AXES for axis in requested_axes)
    ):
        raise IntegratedAnalysisError("integrated_request_invalid")
    by_axis: dict[str, AxisEvidence] = {}
    for evidence in axis_evidence:
        _validate_axis_evidence(evidence, company_id=company_id)
        if evidence.axis in by_axis:
            raise IntegratedAnalysisError("axis_evidence_duplicate")
        by_axis[evidence.axis] = evidence
    if set(by_axis) != set(requested_axes):
        raise IntegratedAnalysisError("axis_evidence_incomplete")

    ready_axes = tuple(axis for axis in requested_axes if by_axis[axis].status == READY_STATUS)
    unavailable_axes = tuple(axis for axis in requested_axes if axis not in ready_axes)
    if len(ready_axes) == len(requested_axes):
        status = "analysis_ready"
    elif ready_axes:
        status = "ready_partial"
    else:
        status = "failed_no_ready_axis"
    observations = _build_observations(
        company_id=company_id,
        evidence_by_axis=by_axis,
        descriptors=descriptors,
    )
    return IntegratedAnalysis(
        status=status,
        company_id=company_id,
        requested_axes=requested_axes,
        ready_axes=ready_axes,
        unavailable_axes=unavailable_axes,
        observations=observations,
    )


def _validate_axis_evidence(evidence: AxisEvidence, *, company_id: str) -> None:
    if evidence.axis not in ANALYSIS_AXES or evidence.company_id != company_id:
        raise IntegratedAnalysisError("axis_company_binding_invalid")
    if evidence.status == READY_STATUS:
        if (
            not evidence.evidence_ids
            or len(evidence.evidence_ids) != len(evidence.citation_ids)
            or any(not SAFE_HASH.fullmatch(value) for value in evidence.evidence_ids)
            or any(not SAFE_HASH.fullmatch(value) for value in evidence.citation_ids)
        ):
            raise IntegratedAnalysisError("ready_axis_citation_invalid")
    elif evidence.status == "unavailable":
        if evidence.evidence_ids or evidence.citation_ids or not evidence.limitation:
            raise IntegratedAnalysisError("unavailable_axis_contract_invalid")
    else:
        raise IntegratedAnalysisError("axis_status_invalid")


def _build_observations(
    *,
    company_id: str,
    evidence_by_axis: dict[str, AxisEvidence],
    descriptors: tuple[ComparisonDescriptor, ...],
) -> tuple[CrossAxisObservation, ...]:
    if any(
        item.company_id != company_id or item.axis not in {"report", "financial"}
        for item in descriptors
    ):
        raise IntegratedAnalysisError("comparison_descriptor_scope_invalid")
    if not {"report", "financial"}.issubset(evidence_by_axis):
        return ()
    if any(evidence_by_axis[axis].status != READY_STATUS for axis in ("report", "financial")):
        return ()

    report = [item for item in descriptors if item.axis == "report"]
    financial = [item for item in descriptors if item.axis == "financial"]
    observations: list[CrossAxisObservation] = []
    for report_item in report:
        _validate_descriptor(
            report_item,
            company_id=company_id,
            expected_role="forecast",
            evidence=evidence_by_axis["report"],
        )
        for financial_item in financial:
            _validate_descriptor(
                financial_item,
                company_id=company_id,
                expected_role="actual",
                evidence=evidence_by_axis["financial"],
            )
            if (report_item.metric, report_item.unit) != (
                financial_item.metric,
                financial_item.unit,
            ):
                continue
            comparison_type = (
                "direction_consistent"
                if report_item.direction == financial_item.direction
                else "direction_divergent"
            )
            payload = {
                "company_id": company_id,
                "comparison_type": comparison_type,
                "metric": report_item.metric,
                "report_period": report_item.period,
                "financial_period": financial_item.period,
                "unit": report_item.unit,
                "report_evidence_id": report_item.evidence_id,
                "financial_evidence_id": financial_item.evidence_id,
                "report_citation_id": report_item.citation_id,
                "financial_citation_id": financial_item.citation_id,
                "limitation": "actual_and_forecast_remain_separate",
            }
            observations.append(
                CrossAxisObservation(observation_id=stable_hash(payload), **payload)
            )
    return tuple(observations)


def _validate_descriptor(
    descriptor: ComparisonDescriptor,
    *,
    company_id: str,
    expected_role: str,
    evidence: AxisEvidence,
) -> None:
    if (
        descriptor.company_id != company_id
        or descriptor.source_role != expected_role
        or not descriptor.metric
        or not descriptor.period
        or not descriptor.unit
        or descriptor.direction not in {"up", "down", "flat"}
        or descriptor.evidence_id not in evidence.evidence_ids
        or descriptor.citation_id not in evidence.citation_ids
    ):
        raise IntegratedAnalysisError("comparison_descriptor_invalid")
