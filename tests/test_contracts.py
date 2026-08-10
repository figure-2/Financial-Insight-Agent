from __future__ import annotations

import json
import sys
import unittest
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fia_public.contracts import ContractError, validate_replay  # noqa: E402


class ReplayContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.payload = json.loads(
            (ROOT / "demo" / "ncsoft-four-axis-replay.json").read_text(encoding="utf-8")
        )

    def test_approved_replay_is_valid(self) -> None:
        replay = validate_replay(self.payload)
        self.assertEqual(
            replay["axis_counts"], {"report": 1, "financial": 6, "legal": 1, "market": 5}
        )
        self.assertTrue(all(value == 0 for value in replay["side_effect_counters"].values()))

    def test_tampered_claim_fails_closed(self) -> None:
        value = deepcopy(self.payload)
        value["sections"][0]["claims"][0]["text"] += " changed"
        with self.assertRaises(ContractError):
            validate_replay(value)

    def test_open_side_effect_boundary_fails_closed(self) -> None:
        value = deepcopy(self.payload)
        value["side_effect_counters"]["network_call_count"] = 1
        with self.assertRaises(ContractError):
            validate_replay(value)


if __name__ == "__main__":
    unittest.main()
