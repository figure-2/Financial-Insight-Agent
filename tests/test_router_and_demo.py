from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fia_public.controlled_router import SUPPORTED_COMPANY_ID  # noqa: E402
from fia_public.evidence_assembly import EvidenceAssembler  # noqa: E402
from fia_public.public_demo import PublicDemoApp  # noqa: E402


class RouterAndDemoTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.assembler = EvidenceAssembler.from_path(ROOT / "demo" / "ncsoft-four-axis-replay.json")
        cls.app = PublicDemoApp(cls.assembler)

    def test_all_recorded_scenarios_are_deterministic(self) -> None:
        for scenario in self.assembler.scenarios:
            first = self.assembler.answer(scenario["question"], company_id=SUPPORTED_COMPANY_ID)
            second = self.assembler.answer(scenario["question"], company_id=SUPPORTED_COMPANY_ID)
            self.assertEqual(first, second)
            self.assertEqual(first["status"], "ready")
            self.assertEqual(first["unsupported_claim_count"], 0)

    def test_supported_paraphrases_route(self) -> None:
        questions = {
            "report": "엔씨소프트 증권사 전망을 보여줘",
            "financial": "엔씨소프트 매출과 영업이익 추세는?",
            "legal": "엔씨소프트 전자금융 규제 적용 근거는?",
            "market": "엔씨소프트 시가총액과 동종 기업 비교를 보여줘",
            "combined": "엔씨소프트 기업분석을 종합해서 보여줘",
        }
        for intent, question in questions.items():
            result = self.assembler.answer(question, company_id=SUPPORTED_COMPANY_ID)
            self.assertEqual(result["intent"], intent)

    def test_ambiguous_and_unsupported_requests_are_blocked(self) -> None:
        ambiguous = self.assembler.answer(
            "매출과 주가를 같이 알려줘", company_id=SUPPORTED_COMPANY_ID
        )
        unsupported = self.assembler.answer("날씨를 알려줘", company_id=SUPPORTED_COMPANY_ID)
        wrong_company = self.assembler.answer("재무 추세를 알려줘", company_id="krx:000000")
        self.assertEqual(ambiguous["reason_code"], "clarification_required")
        self.assertEqual(unsupported["status"], "unsupported")
        self.assertEqual(wrong_company["reason_code"], "company_not_supported")

    def test_api_is_get_only_and_returns_json(self) -> None:
        scenario = self.assembler.scenarios[0]
        query = {"company_id": SUPPORTED_COMPANY_ID, "question": scenario["question"]}
        status, content_type, body = self.app.handle("GET", "/api/analysis", query)
        self.assertEqual(status, 200)
        self.assertEqual(content_type, "application/json; charset=utf-8")
        self.assertEqual(json.loads(body)["status"], "ready")
        self.assertEqual(self.app.handle("POST", "/api/analysis", query)[0], 405)


if __name__ == "__main__":
    unittest.main()
