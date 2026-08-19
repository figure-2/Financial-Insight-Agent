from __future__ import annotations

import sys
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fia_public.contracts import stable_hash  # noqa: E402
from fia_public.durable_runtime import (  # noqa: E402
    DurableJobRepository,
    DurableRuntimeError,
    JobRequest,
)


class DurableRuntimeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.now = datetime(2026, 8, 19, 12, tzinfo=UTC)
        self.owner = stable_hash("worker-a")
        self.request = JobRequest(
            company_id="krx:000001",
            requested_axes=("financial", "report"),
            analysis_as_of="2026-08-19",
            question_hash=stable_hash("private-question-placeholder"),
            policy_version="public-runtime.v1",
        )

    def test_duplicate_request_creates_one_job(self) -> None:
        repository = DurableJobRepository()
        first, first_created = repository.create_or_get(self.request)
        second, second_created = repository.create_or_get(self.request)
        self.assertTrue(first_created)
        self.assertFalse(second_created)
        self.assertEqual(first.job_id, second.job_id)
        self.assertEqual(len(repository.snapshot()), 1)

    def test_restart_snapshot_preserves_idempotency(self) -> None:
        first_repository = DurableJobRepository()
        first, _ = first_repository.create_or_get(self.request)
        restarted = DurableJobRepository(first_repository.snapshot())
        second, created = restarted.create_or_get(self.request)
        self.assertFalse(created)
        self.assertEqual(second.job_id, first.job_id)

    def test_lease_and_revision_guard_state_transitions(self) -> None:
        repository = DurableJobRepository()
        queued, _ = repository.create_or_get(self.request)
        claimed = repository.claim(
            queued.job_id,
            owner_hash=self.owner,
            now=self.now,
            ttl=timedelta(seconds=30),
        )
        acquiring = repository.transition(
            queued.job_id,
            owner_hash=self.owner,
            expected_revision=claimed.revision,
            next_status="acquiring",
            now=self.now,
        )
        self.assertEqual(acquiring.status, "acquiring")
        with self.assertRaises(DurableRuntimeError):
            repository.transition(
                queued.job_id,
                owner_hash=self.owner,
                expected_revision=claimed.revision,
                next_status="validating",
                now=self.now,
            )

    def test_other_owner_and_expired_lease_fail_closed(self) -> None:
        repository = DurableJobRepository()
        queued, _ = repository.create_or_get(self.request)
        claimed = repository.claim(
            queued.job_id,
            owner_hash=self.owner,
            now=self.now,
            ttl=timedelta(seconds=1),
        )
        with self.assertRaises(DurableRuntimeError):
            repository.claim(
                queued.job_id,
                owner_hash=stable_hash("worker-b"),
                now=self.now,
                ttl=timedelta(seconds=30),
            )
        with self.assertRaises(DurableRuntimeError):
            repository.transition(
                queued.job_id,
                owner_hash=self.owner,
                expected_revision=claimed.revision,
                next_status="acquiring",
                now=self.now + timedelta(seconds=2),
            )

    def test_terminal_failure_requires_reason_and_releases_lease(self) -> None:
        repository = DurableJobRepository()
        queued, _ = repository.create_or_get(self.request)
        claimed = repository.claim(
            queued.job_id,
            owner_hash=self.owner,
            now=self.now,
            ttl=timedelta(seconds=30),
        )
        with self.assertRaises(DurableRuntimeError):
            repository.transition(
                queued.job_id,
                owner_hash=self.owner,
                expected_revision=claimed.revision,
                next_status="failed",
                now=self.now,
            )
        failed = repository.transition(
            queued.job_id,
            owner_hash=self.owner,
            expected_revision=claimed.revision,
            next_status="failed",
            reason_code="source_unavailable",
            now=self.now,
        )
        self.assertIsNone(failed.lease_owner_hash)
        self.assertIsNone(failed.lease_expires_at)


if __name__ == "__main__":
    unittest.main()
