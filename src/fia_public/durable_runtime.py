"""Storage-neutral durable job, lease, and idempotency contracts."""

from __future__ import annotations

import secrets
from dataclasses import asdict, dataclass, replace
from datetime import UTC, datetime, timedelta
from typing import Any

from .contracts import SAFE_HASH, stable_hash

SUPPORTED_AXES = ("report", "financial", "market")
TERMINAL_STATUSES = {"ready", "unavailable", "failed"}
ALLOWED_TRANSITIONS = {
    "queued": {"acquiring", "unavailable", "failed"},
    "acquiring": {"validating", "unavailable", "failed"},
    "validating": {"ready", "unavailable", "failed"},
    "ready": set(),
    "unavailable": set(),
    "failed": set(),
}


class DurableRuntimeError(ValueError):
    """Raised when a job or lease transition fails closed."""


@dataclass(frozen=True)
class JobRequest:
    company_id: str
    requested_axes: tuple[str, ...]
    analysis_as_of: str
    question_hash: str
    policy_version: str

    def __post_init__(self) -> None:
        if (
            not self.company_id.startswith("krx:")
            or not self.requested_axes
            or tuple(sorted(set(self.requested_axes))) != self.requested_axes
            or any(axis not in SUPPORTED_AXES for axis in self.requested_axes)
            or not SAFE_HASH.fullmatch(self.question_hash)
            or not self.analysis_as_of
            or not self.policy_version
        ):
            raise DurableRuntimeError("job_request_invalid")

    @property
    def request_key(self) -> str:
        return stable_hash(asdict(self))


@dataclass(frozen=True)
class JobRecord:
    job_id: str
    request_key: str
    company_id: str
    requested_axes: tuple[str, ...]
    status: str
    revision: int
    lease_owner_hash: str | None = None
    lease_expires_at: str | None = None
    reason_code: str | None = None


class DurableJobRepository:
    """Reference repository showing atomic create, lease, and restart semantics."""

    def __init__(self, snapshot: tuple[dict[str, Any], ...] = ()) -> None:
        self._records: dict[str, JobRecord] = {}
        self._request_index: dict[str, str] = {}
        for payload in snapshot:
            record = JobRecord(**payload)
            if record.job_id in self._records or record.request_key in self._request_index:
                raise DurableRuntimeError("job_snapshot_duplicate")
            self._validate_record(record)
            self._records[record.job_id] = record
            self._request_index[record.request_key] = record.job_id

    def create_or_get(self, request: JobRequest) -> tuple[JobRecord, bool]:
        existing_id = self._request_index.get(request.request_key)
        if existing_id is not None:
            return self._records[existing_id], False
        record = JobRecord(
            job_id="job_" + secrets.token_urlsafe(18),
            request_key=request.request_key,
            company_id=request.company_id,
            requested_axes=request.requested_axes,
            status="queued",
            revision=0,
        )
        self._records[record.job_id] = record
        self._request_index[record.request_key] = record.job_id
        return record, True

    def claim(
        self,
        job_id: str,
        *,
        owner_hash: str,
        now: datetime,
        ttl: timedelta,
    ) -> JobRecord:
        record = self.get(job_id)
        observed_at = _aware(now)
        if not SAFE_HASH.fullmatch(owner_hash) or ttl <= timedelta(0):
            raise DurableRuntimeError("lease_contract_invalid")
        if record.status in TERMINAL_STATUSES:
            raise DurableRuntimeError("terminal_job_not_claimable")
        expires_at = _parse_time(record.lease_expires_at)
        lease_active = expires_at is not None and expires_at > observed_at
        if lease_active and record.lease_owner_hash != owner_hash:
            raise DurableRuntimeError("lease_held_by_other_owner")
        claimed = replace(
            record,
            lease_owner_hash=owner_hash,
            lease_expires_at=(observed_at + ttl).isoformat(),
            revision=record.revision + 1,
        )
        self._records[job_id] = claimed
        return claimed

    def transition(
        self,
        job_id: str,
        *,
        owner_hash: str,
        expected_revision: int,
        next_status: str,
        now: datetime,
        reason_code: str | None = None,
    ) -> JobRecord:
        record = self.get(job_id)
        observed_at = _aware(now)
        expires_at = _parse_time(record.lease_expires_at)
        if (
            record.revision != expected_revision
            or record.lease_owner_hash != owner_hash
            or expires_at is None
            or expires_at <= observed_at
        ):
            raise DurableRuntimeError("lease_or_revision_lost")
        if next_status not in ALLOWED_TRANSITIONS.get(record.status, set()):
            raise DurableRuntimeError("job_transition_invalid")
        if next_status in {"unavailable", "failed"} and not reason_code:
            raise DurableRuntimeError("terminal_reason_required")
        transitioned = replace(
            record,
            status=next_status,
            reason_code=reason_code,
            revision=record.revision + 1,
            lease_owner_hash=None if next_status in TERMINAL_STATUSES else owner_hash,
            lease_expires_at=None if next_status in TERMINAL_STATUSES else record.lease_expires_at,
        )
        self._records[job_id] = transitioned
        return transitioned

    def get(self, job_id: str) -> JobRecord:
        try:
            return self._records[job_id]
        except KeyError as exc:
            raise DurableRuntimeError("job_not_found") from exc

    def snapshot(self) -> tuple[dict[str, Any], ...]:
        return tuple(asdict(self._records[key]) for key in sorted(self._records))

    @staticmethod
    def _validate_record(record: JobRecord) -> None:
        if (
            not record.job_id.startswith("job_")
            or not SAFE_HASH.fullmatch(record.request_key)
            or record.status not in ALLOWED_TRANSITIONS
            or record.revision < 0
        ):
            raise DurableRuntimeError("job_snapshot_invalid")


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise DurableRuntimeError("lease_time_timezone_required")
    return value.astimezone(UTC)


def _parse_time(value: str | None) -> datetime | None:
    if value is None:
        return None
    try:
        return _aware(datetime.fromisoformat(value))
    except ValueError as exc:
        raise DurableRuntimeError("lease_time_invalid") from exc
