"""Controlled intent routing without model or provider calls."""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

SUPPORTED_COMPANY_ID = "krx:036570"
_SUPPORTED_ALIASES = ("엔씨소프트", "ncsoft", "nc soft", "036570", SUPPORTED_COMPANY_ID)
_KEYWORDS = {
    "report": ("리포트", "증권사", "전망", "report", "outlook"),
    "financial": ("재무", "매출", "영업이익", "순이익", "실적", "dart"),
    "legal": ("법령", "법적", "규제", "적용", "전자금융", "regulation"),
    "market": ("시장", "시가총액", "동종", "peer", "valuation", "per", "주가"),
}
_COMBINED_MARKERS = ("종합", "기업분석", "모두", "함께 요약", "주요 재무 및 법적")


@dataclass(frozen=True)
class RouteDecision:
    status: str
    intent: str | None
    reason_code: str | None


def normalize_question(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).casefold().strip()
    return re.sub(r"\s+", " ", normalized)


def route_question(
    question: str,
    *,
    company_id: str,
    scenarios: Sequence[Mapping[str, object]],
) -> RouteDecision:
    if company_id != SUPPORTED_COMPANY_ID:
        return RouteDecision("unsupported", None, "company_not_supported")
    if not isinstance(question, str) or not question.strip() or len(question) > 500:
        return RouteDecision("unsupported", None, "question_invalid")
    normalized = normalize_question(question)
    exact = {normalize_question(str(item["question"])): str(item["intent"]) for item in scenarios}
    if normalized in exact:
        return RouteDecision("routed", exact[normalized], None)

    compact = re.sub(r"[\s:_-]+", "", normalized)
    mentioned_supported = any(
        re.sub(r"[\s:_-]+", "", normalize_question(alias)) in compact
        for alias in _SUPPORTED_ALIASES
    )
    if re.search(r"\bkrx:\d{6}\b|(?<!\d)\d{6}(?!\d)", normalized) and not mentioned_supported:
        return RouteDecision("unsupported", None, "company_not_supported")

    scores = {
        intent: sum(1 for keyword in keywords if keyword in normalized)
        for intent, keywords in _KEYWORDS.items()
    }
    active = [intent for intent, score in scores.items() if score > 0]
    if len(active) >= 2:
        if any(marker in normalized for marker in _COMBINED_MARKERS):
            return RouteDecision("routed", "combined", None)
        return RouteDecision("clarification_required", None, "clarification_required")
    if len(active) == 1:
        return RouteDecision("routed", active[0], None)
    if any(marker in normalized for marker in _COMBINED_MARKERS):
        return RouteDecision("routed", "combined", None)
    return RouteDecision("unsupported", None, "question_not_supported")
