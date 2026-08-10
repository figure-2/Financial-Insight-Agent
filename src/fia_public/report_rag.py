"""Question-scoped Report RAG projection."""

from __future__ import annotations

from typing import Any

from .contracts import ContractError


def project_report(section: dict[str, Any]) -> dict[str, Any]:
    claims = section.get("claims")
    if section.get("axis") != "report" or not isinstance(claims, list) or len(claims) != 1:
        raise ContractError("report_projection_invalid")
    locator = claims[0]["locator"]["value"]
    bbox = locator.get("bbox")
    if (
        not isinstance(locator.get("page_number"), int)
        or not isinstance(bbox, list)
        or len(bbox) != 4
    ):
        raise ContractError("report_locator_invalid")
    return {"axis": "report", "claims": claims}
