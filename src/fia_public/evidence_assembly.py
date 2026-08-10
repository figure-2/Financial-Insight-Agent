"""Assemble validated evidence for one controlled question."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from .contracts import ContractError, validate_replay
from .controlled_router import RouteDecision, route_question
from .financial_evidence import project_financial
from .market_analytics import project_market
from .regulatory_evidence import project_regulatory
from .report_rag import project_report

PROJECTORS = {
    "report": project_report,
    "financial": project_financial,
    "legal": project_regulatory,
    "market": project_market,
}


class EvidenceAssembler:
    def __init__(self, replay: Mapping[str, Any]) -> None:
        self.replay = validate_replay(replay)
        self.scenarios = tuple(self.replay["scenarios"])
        self.by_intent = {item["intent"]: item for item in self.scenarios}
        self.sections = {item["axis"]: item for item in self.replay["sections"]}

    @classmethod
    def from_path(cls, path: Path) -> EvidenceAssembler:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise ContractError("replay_read_failed") from exc
        return cls(payload)

    def answer(self, question: str, *, company_id: str) -> dict[str, Any]:
        decision = route_question(question, company_id=company_id, scenarios=self.scenarios)
        if decision.status != "routed" or decision.intent is None:
            return _guarded(decision)
        scenario = self.by_intent[decision.intent]
        selected = [PROJECTORS[axis](self.sections[axis]) for axis in scenario["selected_axes"]]
        return {
            "status": "ready",
            "intent": decision.intent,
            "scenario_id": scenario["scenario_id"],
            "question": scenario["question"],
            "sections": selected,
            "answer_summary": self.replay["answer_summaries"][decision.intent],
            "limitations": list(self.replay["limitations"]),
            "unsupported_claim_count": 0,
            "side_effect_counters": dict(self.replay["side_effect_counters"]),
        }


def _guarded(decision: RouteDecision) -> dict[str, Any]:
    return {
        "status": decision.status,
        "reason_code": decision.reason_code,
        "unsupported_claim_count": 0,
        "side_effect_counters": {
            "provider_call_count": 0,
            "network_call_count": 0,
            "llm_call_count": 0,
            "final_answer_call_count": 0,
            "db_write_count": 0,
            "vector_write_count": 0,
        },
    }
