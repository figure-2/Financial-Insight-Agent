"""Fail-closed metadata and prefix checks for untrusted report PDFs."""

from __future__ import annotations

from dataclasses import dataclass


class PdfSecurityError(ValueError):
    """Raised when an untrusted PDF cannot enter the parser boundary."""


@dataclass(frozen=True)
class PdfSecurityPolicy:
    allowed_hosts: tuple[str, ...]
    maximum_response_bytes: int = 20 * 1024 * 1024
    maximum_pages: int = 300
    maximum_objects: int = 100_000

    def __post_init__(self) -> None:
        if (
            not self.allowed_hosts
            or any(not host or "/" in host for host in self.allowed_hosts)
            or self.maximum_response_bytes <= 0
            or self.maximum_pages <= 0
            or self.maximum_objects <= 0
        ):
            raise PdfSecurityError("pdf_security_policy_invalid")


@dataclass(frozen=True)
class PdfIntakeMetadata:
    host: str
    content_type: str
    response_bytes: int
    body_prefix: bytes
    page_count: int
    object_count: int
    encrypted: bool = False
    active_content: bool = False
    embedded_file: bool = False
    parser_timed_out: bool = False


@dataclass(frozen=True)
class PdfSecurityDecision:
    status: str
    parser_allowed: bool


def validate_pdf_for_parser(
    metadata: PdfIntakeMetadata,
    *,
    policy: PdfSecurityPolicy,
) -> PdfSecurityDecision:
    if metadata.host not in policy.allowed_hosts:
        return PdfSecurityDecision("rejected_host", False)
    normalized_type = metadata.content_type.split(";", 1)[0].strip().casefold()
    if normalized_type != "application/pdf":
        return PdfSecurityDecision("rejected_content_type", False)
    if not metadata.body_prefix.startswith(b"%PDF-"):
        return PdfSecurityDecision("rejected_signature", False)
    if not 0 < metadata.response_bytes <= policy.maximum_response_bytes:
        return PdfSecurityDecision("rejected_size", False)
    if metadata.encrypted:
        return PdfSecurityDecision("rejected_encrypted", False)
    if metadata.active_content:
        return PdfSecurityDecision("rejected_active_content", False)
    if metadata.embedded_file:
        return PdfSecurityDecision("rejected_embedded_file", False)
    if (
        not 0 < metadata.page_count <= policy.maximum_pages
        or not 0 < metadata.object_count <= policy.maximum_objects
    ):
        return PdfSecurityDecision("rejected_page_or_object_limit", False)
    if metadata.parser_timed_out:
        return PdfSecurityDecision("parser_timeout", False)
    return PdfSecurityDecision("validated_for_parser", True)
