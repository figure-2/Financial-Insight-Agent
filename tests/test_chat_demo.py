from __future__ import annotations

import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fia_public.evidence_assembly import EvidenceAssembler  # noqa: E402
from fia_public.public_demo import PUBLIC_FILES, PublicDemoApp  # noqa: E402


class ChatDemoTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = PublicDemoApp(
            EvidenceAssembler.from_path(ROOT / "demo" / "ncsoft-four-axis-replay.json")
        )
        cls.data = json.loads((ROOT / "demo" / "chat-scenarios.json").read_text("utf-8"))

    def test_site_links_and_scripts_resolve_through_explicit_routes(self) -> None:
        for route in ("/", "/chat"):
            status, media, html = self.app.handle("GET", route, {})
            self.assertEqual(status, 200)
            self.assertIn("text/html", media)
            for target in re.findall(r'(?:href|src)="(/[^"?#]*)(?:[?#][^"]*)?"', html):
                self.assertEqual(self.app.handle("GET", target, {})[0], 200, target)
        for route, (_, media) in PUBLIC_FILES.items():
            self.assertEqual(self.app.handle("GET", route, {})[1], media)

    def test_asset_route_rejects_files_outside_allowlist(self) -> None:
        for path in ("/README.md", "/assets/../run.py", "/web/chat.html", "/assets/missing.js"):
            self.assertEqual(self.app.handle("GET", path, {})[0], 404)
        self.assertEqual(self.app.handle("POST", "/chat", {})[0], 405)

    def test_recorded_example_page_remains_available(self) -> None:
        status, _, body = self.app.handle("GET", "/replay", {})
        self.assertEqual(status, 200)
        self.assertIn('action="/analysis"', body)

    def test_synthetic_values_and_source_roles_are_consistent(self) -> None:
        self.assertEqual(self.data["mode"], "synthetic")
        self.assertEqual(set(self.data["sources"]), {"report", "financial", "legal", "market"})
        financial = self.data["financial"]
        self.assertEqual(financial["operating_income"] / financial["revenue"] * 100, 15)
        self.assertEqual(self.data["market"][-1]["close"] - self.data["market"][0]["close"], 500)
        self.assertEqual(len({row["date"] for row in self.data["market"]}), 5)
        self.assertTrue(all(source["excerpt"] for source in self.data["sources"].values()))
        self.assertIn("가상 조문", self.data["sources"]["legal"]["title"])

    def test_browser_demo_uses_text_nodes_and_tab_memory(self) -> None:
        script = (ROOT / "web" / "chat.mjs").read_text("utf-8")
        self.assertNotRegex(
            script, r"innerHTML|outerHTML|insertAdjacentHTML|localStorage|sessionStorage"
        )
        self.assertNotRegex(script, r"https?://(?!www\.w3\.org/2000/svg)")
        self.assertIn('fetch("/assets/scenarios.json"', script)
        self.assertIn("textContent", script)
        self.assertIn("isComposing", script)

    def test_container_packages_website_files(self) -> None:
        self.assertIn("COPY --chown=fia:fia web /app/web", (ROOT / "Dockerfile").read_text())


if __name__ == "__main__":
    unittest.main()
