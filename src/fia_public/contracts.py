"""Validation contracts for the sanitized recorded replay."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from copy import deepcopy
from typing import Any

REPLAY_SCHEMA = "fia.public-safe-four-axis-replay.v1"
REPLAY_MODE = "sanitized_recorded_four_axis_replay"
AXIS_ORDER = ("report", "financial", "legal", "market")
AXIS_COUNTS = {"report": 1, "financial": 6, "legal": 1, "market": 5}
INTENT_AXES = {
    "combined": AXIS_ORDER,
    "report": ("report",),
    "financial": ("financial",),
    "legal": ("legal",),
    "market": ("financial", "market"),
}
SAFE_HASH = re.compile(r"^sha256:[0-9a-f]{64}$")
UNSAFE_TEXT = re.compile(
    r"(?:[A-Za-z]:\\|/Users/|/home/|"
    r"\b(?:api[_ -]?key|password|secret|credential)\s*[:=]|"
    r"\bBearer\s+[A-Za-z0-9._-]{12,})",
    re.IGNORECASE,
)
CONTACT_TEXT = re.compile(
    r"(?:\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b|"
    r"(?<!\d)(?:(?:\+?82[- .]?\d{1,2})|(?:0\d{1,2}))[- .]?\d{3,4}[- .]\d{4}(?!\d))",
    re.IGNORECASE,
)
UNSAFE_KEYS = {
    "api_key",
    "authorization",
    "credential",
    "file_path",
    "local_path",
    "password",
    "raw_body",
    "raw_payload",
    "raw_response",
    "raw_text",
    "secret",
    "token",
    "uri",
}


class ContractError(ValueError):
    """Raised when public data violates a fail-closed contract."""


def stable_hash(value: Any) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def validate_replay(value: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ContractError("replay_invalid")
    replay = deepcopy(dict(value))
    if replay.get("schema_version") != REPLAY_SCHEMA:
        raise ContractError("replay_schema_invalid")
    if replay.get("demo_mode") != REPLAY_MODE:
        raise ContractError("replay_mode_invalid")
    if replay.get("status") != "ready" or replay.get("live_runtime") is not False:
        raise ContractError("replay_status_invalid")
    if replay.get("axis_counts") != AXIS_COUNTS:
        raise ContractError("axis_counts_invalid")
    if replay.get("unsupported_claim_count") != 0:
        raise ContractError("unsupported_claim_present")
    if contains_unsafe_value(replay):
        raise ContractError("unsafe_public_value")
    _validate_counters(replay.get("side_effect_counters"))
    references = _validate_sections(replay.get("sections"))
    _validate_scenarios(replay.get("scenarios"))
    _validate_summaries(replay.get("answer_summaries"), references)
    receipt = {
        "axis_counts": replay["axis_counts"],
        "sections": replay["sections"],
        "answer_summaries": replay["answer_summaries"],
    }
    if replay.get("recorded_source_receipt_hash") != stable_hash(receipt):
        raise ContractError("receipt_hash_invalid")
    replay_id = replay.get("replay_id")
    if not isinstance(replay_id, str) or not SAFE_HASH.fullmatch(replay_id):
        raise ContractError("replay_id_invalid")
    payload = {key: item for key, item in replay.items() if key != "replay_id"}
    if replay_id != stable_hash(payload):
        raise ContractError("replay_id_invalid")
    return replay


def contains_unsafe_value(value: Any, key: str | None = None) -> bool:
    if key is not None and key.casefold() in UNSAFE_KEYS:
        return True
    if isinstance(value, str):
        return bool(UNSAFE_TEXT.search(value) or CONTACT_TEXT.search(value))
    if isinstance(value, Mapping):
        return any(contains_unsafe_value(item, str(name)) for name, item in value.items())
    if isinstance(value, (list, tuple)):
        return any(contains_unsafe_value(item) for item in value)
    return False


def _validate_counters(value: Any) -> None:
    if not isinstance(value, dict) or not value:
        raise ContractError("side_effect_boundary_invalid")
    if any(
        isinstance(number, bool) or not isinstance(number, int) or number != 0
        for number in value.values()
    ):
        raise ContractError("side_effect_boundary_open")


def _validate_sections(value: Any) -> dict[str, set[tuple[str, str]]]:
    if not isinstance(value, list) or [item.get("axis") for item in value] != list(AXIS_ORDER):
        raise ContractError("sections_invalid")
    references: dict[str, set[tuple[str, str]]] = {}
    for section in value:
        axis = section["axis"]
        claims = section.get("claims")
        if not isinstance(claims, list) or len(claims) != AXIS_COUNTS[axis]:
            raise ContractError("claim_count_invalid")
        axis_refs: set[tuple[str, str]] = set()
        for claim in claims:
            required = {"claim_id", "citation_id", "source_hash", "text", "locator"}
            if not isinstance(claim, dict) or not required.issubset(claim):
                raise ContractError("claim_invalid")
            if not isinstance(claim["text"], str) or not claim["text"].strip():
                raise ContractError("claim_text_invalid")
            if not SAFE_HASH.fullmatch(str(claim["citation_id"])):
                raise ContractError("citation_hash_invalid")
            if not SAFE_HASH.fullmatch(str(claim["source_hash"])):
                raise ContractError("source_hash_invalid")
            locator = claim["locator"]
            if not isinstance(locator, dict) or not isinstance(locator.get("value"), dict):
                raise ContractError("locator_invalid")
            if any(
                name.endswith("_hash") and not SAFE_HASH.fullmatch(str(item))
                for name, item in locator["value"].items()
            ):
                raise ContractError("locator_hash_invalid")
            axis_refs.add((str(claim["citation_id"]), str(claim["source_hash"])))
        references[axis] = axis_refs
    return references


def _validate_scenarios(value: Any) -> None:
    if not isinstance(value, list) or len(value) != len(INTENT_AXES):
        raise ContractError("scenario_contract_invalid")
    intents: set[str] = set()
    for scenario in value:
        if not isinstance(scenario, dict):
            raise ContractError("scenario_contract_invalid")
        intent = scenario.get("intent")
        if intent not in INTENT_AXES or intent in intents:
            raise ContractError("scenario_contract_invalid")
        if tuple(scenario.get("selected_axes", ())) != INTENT_AXES[intent]:
            raise ContractError("scenario_axes_invalid")
        if scenario.get("expected_status") != "ready":
            raise ContractError("scenario_status_invalid")
        if scenario.get("answer_status") not in {"pass", "pass_with_limitations"}:
            raise ContractError("scenario_answer_status_invalid")
        for field in ("scenario_id", "label", "question"):
            if not isinstance(scenario.get(field), str) or not scenario[field].strip():
                raise ContractError("scenario_contract_invalid")
        intents.add(intent)


def _validate_summaries(value: Any, references: dict[str, set[tuple[str, str]]]) -> None:
    if not isinstance(value, dict) or set(value) != set(INTENT_AXES):
        raise ContractError("summary_contract_invalid")
    for intent, summary in value.items():
        if not isinstance(summary, dict):
            raise ContractError("summary_contract_invalid")
        observations = summary.get("observations")
        payload = {
            "status": summary.get("status"),
            "observation_count": summary.get("observation_count"),
            "observations": observations,
        }
        if (
            summary.get("status") not in {"pass", "pass_with_limitations"}
            or not isinstance(observations, list)
            or not 1 <= len(observations) <= 5
            or summary.get("observation_count") != len(observations)
            or summary.get("summary_hash") != stable_hash(payload)
        ):
            raise ContractError("summary_contract_invalid")
        allowed = set().union(*(references[axis] for axis in INTENT_AXES[intent]))
        for observation in observations:
            if not isinstance(observation, dict):
                raise ContractError("observation_invalid")
            observation_payload = {
                key: item for key, item in observation.items() if key != "observation_id"
            }
            refs = observation.get("citation_refs")
            if (
                observation.get("observation_id") != stable_hash(observation_payload)
                or not isinstance(observation.get("title"), str)
                or not isinstance(observation.get("text"), str)
                or not isinstance(refs, list)
                or not refs
            ):
                raise ContractError("observation_invalid")
            for ref in refs:
                pair = (str(ref.get("citation_id")), str(ref.get("source_hash")))
                if pair not in allowed:
                    raise ContractError("observation_reference_invalid")
