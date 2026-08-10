"""Question-scoped regulatory evidence with applicability limits."""

from __future__ import annotations

from typing import Any

from .contracts import ContractError


def project_regulatory(section: dict[str, Any]) -> dict[str, Any]:
    claims = section.get("claims")
    if section.get("axis") != "legal" or not isinstance(claims, list) or len(claims) != 1:
        raise ContractError("regulatory_projection_invalid")
    locator = claims[0]["locator"]["value"]
    if (
        not isinstance(locator.get("article"), str)
        or not isinstance(locator.get("page_start"), int)
        or not isinstance(locator.get("page_end"), int)
        or not isinstance(locator.get("provision_scope"), str)
    ):
        raise ContractError("regulatory_locator_invalid")
    return {"axis": "legal", "claims": claims}
