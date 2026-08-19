"""Provider-free generic service orchestration over public runtime contracts."""

from __future__ import annotations

from dataclasses import dataclass

from .company_runtime import CompanyRegistry
from .contracts import SAFE_HASH
from .durable_runtime import DurableJobRepository, JobRequest
from .integrated_analysis import (
    ANALYSIS_AXES,
    AxisEvidence,
    ComparisonDescriptor,
    IntegratedAnalysis,
    build_integrated_analysis,
)


class ServiceRuntimeError(ValueError):
    """Raised when a service request or clarification is tampered."""


@dataclass(frozen=True)
class AnalysisRequest:
    company_reference: str
    question_hash: str
    requested_axes: tuple[str, ...]
    analysis_as_of: str

    def __post_init__(self) -> None:
        if (
            not self.company_reference.strip()
            or not SAFE_HASH.fullmatch(self.question_hash)
            or tuple(sorted(set(self.requested_axes))) != self.requested_axes
            or not self.requested_axes
            or any(axis not in ANALYSIS_AXES for axis in self.requested_axes)
            or not self.analysis_as_of
        ):
            raise ServiceRuntimeError("analysis_request_invalid")


@dataclass(frozen=True)
class ServiceResponse:
    http_status: int
    status: str
    company_id: str | None = None
    candidates: tuple[str, ...] = ()
    job_id: str | None = None
    job_created: bool | None = None
    result: IntegratedAnalysis | None = None
    reason_code: str | None = None


class GenericAnalysisService:
    """Resolve identity, reuse terminal evidence, or create one idempotent job."""

    def __init__(
        self,
        *,
        registry: CompanyRegistry,
        jobs: DurableJobRepository,
        evidence: tuple[AxisEvidence, ...] = (),
        descriptors: tuple[ComparisonDescriptor, ...] = (),
    ) -> None:
        self.registry = registry
        self.jobs = jobs
        self.evidence = {(item.company_id, item.axis): item for item in evidence}
        if len(self.evidence) != len(evidence):
            raise ServiceRuntimeError("service_evidence_duplicate")
        self.descriptors = descriptors

    def submit(
        self,
        request: AnalysisRequest,
        *,
        selected_company_id: str | None = None,
    ) -> ServiceResponse:
        resolution = self.registry.resolve(request.company_reference)
        if resolution.status == "clarification_required":
            if selected_company_id is None:
                return ServiceResponse(
                    409,
                    "clarification_required",
                    candidates=resolution.candidates,
                    reason_code=resolution.reason_code,
                )
            if selected_company_id not in resolution.candidates:
                raise ServiceRuntimeError("clarification_selection_invalid")
            company_id = selected_company_id
        elif resolution.status == "resolved" and resolution.company_id is not None:
            if selected_company_id is not None and selected_company_id != resolution.company_id:
                raise ServiceRuntimeError("clarification_selection_unexpected")
            company_id = resolution.company_id
        else:
            return ServiceResponse(404, "unavailable", reason_code=resolution.reason_code)

        selected_evidence = tuple(
            self.evidence[(company_id, axis)]
            for axis in request.requested_axes
            if (company_id, axis) in self.evidence
        )
        if len(selected_evidence) != len(request.requested_axes):
            job, created = self.jobs.create_or_get(
                JobRequest(
                    company_id=company_id,
                    requested_axes=request.requested_axes,
                    analysis_as_of=request.analysis_as_of,
                    question_hash=request.question_hash,
                    policy_version="public-service.v1",
                )
            )
            return ServiceResponse(
                202,
                "acquisition_in_progress",
                company_id=company_id,
                job_id=job.job_id,
                job_created=created,
            )

        result = build_integrated_analysis(
            company_id=company_id,
            requested_axes=request.requested_axes,
            axis_evidence=selected_evidence,
            descriptors=tuple(
                item for item in self.descriptors if item.company_id == company_id
            ),
        )
        return ServiceResponse(200, result.status, company_id=company_id, result=result)
