"""Question-scoped financial evidence projection."""

from __future__ import annotations

from typing import Any

from .contracts import ContractError


def project_financial(section: dict[str, Any]) -> dict[str, Any]:
    claims = section.get("claims")
    if section.get("axis") != "financial" or not isinstance(claims, list) or len(claims) != 6:
        raise ContractError("financial_projection_invalid")
    for claim in claims:
        locator = claim["locator"]["value"]
        required = ("display_metric", "display_period", "display_unit", "display_value", "period")
        if any(
            not isinstance(locator.get(name), str) or not locator[name].strip() for name in required
        ):
            raise ContractError("financial_locator_invalid")
    return {"axis": "financial", "claims": claims}
