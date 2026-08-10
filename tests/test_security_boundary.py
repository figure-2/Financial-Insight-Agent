from __future__ import annotations

import ast
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTBOUND_CLIENT_MODULES = {"requests", "http.client", "urllib.request"}
LOCAL_PATH = re.compile(r"(?:[A-Za-z]:\\|/Users/|/home/)")
CONTACT = re.compile(
    r"(?:\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b|(?<!\d)0\d{1,2}[- ]\d{3,4}[- ]\d{4}(?!\d))", re.I
)


class SecurityBoundaryTests(unittest.TestCase):
    def test_runtime_has_no_outbound_client_import(self) -> None:
        found: set[str] = set()
        for path in (ROOT / "src").rglob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    found.update(alias.name for alias in node.names)
                elif isinstance(node, ast.ImportFrom) and node.module:
                    found.add(node.module)
        self.assertTrue(OUTBOUND_CLIENT_MODULES.isdisjoint(found))

    def test_replay_has_no_contact_or_local_path(self) -> None:
        text = (ROOT / "demo" / "ncsoft-four-axis-replay.json").read_text(encoding="utf-8")
        self.assertIsNone(LOCAL_PATH.search(text))
        self.assertIsNone(CONTACT.search(text))
        payload = json.loads(text)
        self.assertFalse(payload["live_runtime"])
        self.assertTrue(all(value == 0 for value in payload["side_effect_counters"].values()))

    def test_candidate_contains_no_symlink(self) -> None:
        self.assertFalse(any(path.is_symlink() for path in ROOT.rglob("*")))


if __name__ == "__main__":
    unittest.main()
