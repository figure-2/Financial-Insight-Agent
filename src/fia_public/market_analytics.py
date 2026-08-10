"""Question-scoped market evidence projection."""

from __future__ import annotations

from typing import Any

from .contracts import ContractError

MARKET_CATEGORIES = {"price", "return", "volatility", "peer", "valuation"}


def project_market(section: dict[str, Any]) -> dict[str, Any]:
    claims = section.get("claims")
    if section.get("axis") != "market" or not isinstance(claims, list) or len(claims) != 5:
        raise ContractError("market_projection_invalid")
    categories: set[str] = set()
    as_of_values: set[str] = set()
    for claim in claims:
        locator = claim["locator"]["value"]
        category = locator.get("evidence_category")
        as_of = locator.get("as_of")
        if category not in MARKET_CATEGORIES or not isinstance(as_of, str) or not as_of:
            raise ContractError("market_locator_invalid")
        categories.add(category)
        as_of_values.add(as_of)
    if categories != MARKET_CATEGORIES or len(as_of_values) != 1:
        raise ContractError("market_category_contract_invalid")
    return {"axis": "market", "claims": claims}
