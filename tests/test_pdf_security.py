from __future__ import annotations

import sys
import unittest
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fia_public.pdf_security import (  # noqa: E402
    PdfIntakeMetadata,
    PdfSecurityPolicy,
    validate_pdf_for_parser,
)


class PdfSecurityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.policy = PdfSecurityPolicy(("reports.example.invalid",))
        self.valid = PdfIntakeMetadata(
            host="reports.example.invalid",
            content_type="application/pdf",
            response_bytes=1024,
            body_prefix=b"%PDF-1.7",
            page_count=12,
            object_count=300,
        )

    def test_valid_metadata_can_cross_parser_boundary(self) -> None:
        decision = validate_pdf_for_parser(self.valid, policy=self.policy)
        self.assertEqual(decision.status, "validated_for_parser")
        self.assertTrue(decision.parser_allowed)

    def test_host_type_signature_and_size_fail_closed(self) -> None:
        mutations = (
            (replace(self.valid, host="other.example.invalid"), "rejected_host"),
            (replace(self.valid, content_type="text/html"), "rejected_content_type"),
            (replace(self.valid, body_prefix=b"not-pdf"), "rejected_signature"),
            (
                replace(self.valid, response_bytes=self.policy.maximum_response_bytes + 1),
                "rejected_size",
            ),
        )
        for metadata, expected in mutations:
            with self.subTest(expected=expected):
                self.assertEqual(
                    validate_pdf_for_parser(metadata, policy=self.policy).status,
                    expected,
                )

    def test_active_encrypted_embedded_and_resource_heavy_pdf_are_rejected(self) -> None:
        mutations = (
            (replace(self.valid, encrypted=True), "rejected_encrypted"),
            (replace(self.valid, active_content=True), "rejected_active_content"),
            (replace(self.valid, embedded_file=True), "rejected_embedded_file"),
            (
                replace(self.valid, page_count=self.policy.maximum_pages + 1),
                "rejected_page_or_object_limit",
            ),
            (replace(self.valid, parser_timed_out=True), "parser_timeout"),
        )
        for metadata, expected in mutations:
            with self.subTest(expected=expected):
                decision = validate_pdf_for_parser(metadata, policy=self.policy)
                self.assertEqual(decision.status, expected)
                self.assertFalse(decision.parser_allowed)


if __name__ == "__main__":
    unittest.main()
