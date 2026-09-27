"""GET-only website, synthetic chat assets, and recorded example API."""

from __future__ import annotations

import argparse
import json
from collections.abc import Mapping, Sequence
from html import escape
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlsplit

from .contracts import REPLAY_MODE, ContractError
from .controlled_router import SUPPORTED_COMPANY_ID
from .evidence_assembly import EvidenceAssembler

ROOT = Path(__file__).resolve().parents[2]
REPLAY_PATH = ROOT / "demo" / "ncsoft-four-axis-replay.json"
PUBLIC_FILES = {
    "/": (ROOT / "web" / "index.html", "text/html; charset=utf-8"),
    "/chat": (ROOT / "web" / "chat.html", "text/html; charset=utf-8"),
    "/assets/app.css": (ROOT / "web" / "app.css", "text/css; charset=utf-8"),
    "/assets/chat.mjs": (ROOT / "web" / "chat.mjs", "text/javascript; charset=utf-8"),
    "/assets/chat-engine.mjs": (ROOT / "web" / "chat-engine.mjs", "text/javascript; charset=utf-8"),
    "/assets/scenarios.json": (
        ROOT / "demo" / "chat-scenarios.json",
        "application/json; charset=utf-8",
    ),
}


class DemoError(ValueError):
    pass


class PublicDemoApp:
    def __init__(self, assembler: EvidenceAssembler) -> None:
        self.assembler = assembler

    def handle(self, method: str, path: str, query: Mapping[str, str]) -> tuple[int, str, str]:
        if method.upper() != "GET":
            return 405, "text/html; charset=utf-8", _error_page("method_not_allowed")
        if path in PUBLIC_FILES:
            source, media_type = PUBLIC_FILES[path]
            return 200, media_type, source.read_text(encoding="utf-8")
        if path == "/replay":
            return 200, "text/html; charset=utf-8", _landing_page(self.assembler.scenarios)
        if path not in {"/analysis", "/api/analysis"}:
            return 404, "text/html; charset=utf-8", _error_page("route_not_found")
        if set(query) != {"company_id", "question"}:
            return 422, "text/html; charset=utf-8", _error_page("query_contract_invalid")
        result = self.assembler.answer(query["question"], company_id=query["company_id"])
        status = 200 if result["status"] == "ready" else 422
        if path == "/api/analysis":
            return (
                status,
                "application/json; charset=utf-8",
                json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
            )
        return status, "text/html; charset=utf-8", _result_page(result)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the evidence-based public prototype.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("smoke")
    serve = subparsers.add_parser("serve")
    serve.add_argument("--port", type=int, default=8765)
    args = parser.parse_args(argv)
    try:
        app = PublicDemoApp(EvidenceAssembler.from_path(REPLAY_PATH))
        if args.command == "smoke":
            return smoke(app)
        if not 1024 <= args.port <= 65535:
            raise DemoError("port_invalid")
        _serve(app, args.port)
        return 0
    except (ContractError, DemoError, OSError, TypeError, ValueError) as exc:
        print(json.dumps({"status": "blocked_by_guard", "reason_code": str(exc)}, sort_keys=True))
        return 1


def smoke(app: PublicDemoApp) -> int:
    rendered: list[str] = []
    for scenario in app.assembler.scenarios:
        query = {"company_id": SUPPORTED_COMPANY_ID, "question": scenario["question"]}
        first = app.handle("GET", "/api/analysis", query)
        second = app.handle("GET", "/api/analysis", query)
        if first != second or first[0] != 200:
            raise DemoError("deterministic_scenario_failed")
        payload = json.loads(first[2])
        if payload["status"] != "ready" or payload["unsupported_claim_count"] != 0:
            raise DemoError("scenario_not_ready")
        if any(payload["side_effect_counters"].values()):
            raise DemoError("side_effect_boundary_open")
        rendered.append(first[2])
    guards = (
        app.handle("GET", "/api/analysis", {"company_id": "krx:000000", "question": "재무 추세"}),
        app.handle(
            "GET",
            "/api/analysis",
            {"company_id": SUPPORTED_COMPANY_ID, "question": "지원 범위 밖 질문"},
        ),
        app.handle(
            "GET",
            "/api/analysis",
            {"company_id": SUPPORTED_COMPANY_ID, "question": "매출과 주가를 같이 알려줘"},
        ),
    )
    if [item[0] for item in guards] != [422, 422, 422]:
        raise DemoError("guard_scenario_failed")
    ambiguous = json.loads(guards[2][2])
    if ambiguous.get("reason_code") != "clarification_required":
        raise DemoError("clarification_guard_failed")
    output = {
        "schema_version": "fia.public-prototype-smoke.v1",
        "status": "ready",
        "demo_mode": REPLAY_MODE,
        "scenario_count": len(rendered),
        "guard_count": len(guards),
        "unsupported_claim_count": 0,
        "provider_call_count": 0,
        "network_call_count": 0,
        "llm_call_count": 0,
        "final_answer_call_count": 0,
    }
    print(json.dumps(output, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    return 0


def _serve(app: PublicDemoApp, port: int) -> None:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            parsed = urlsplit(self.path)
            raw_query = parse_qs(parsed.query, keep_blank_values=True)
            query = {key: values[0] for key, values in raw_query.items() if len(values) == 1}
            status, content_type, body = app.handle("GET", parsed.path, query)
            payload = body.encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header(
                "Content-Security-Policy",
                "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
                "connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'",
            )
            self.end_headers()
            self.wfile.write(payload)

        def do_POST(self) -> None:  # noqa: N802
            status, content_type, body = app.handle("POST", urlsplit(self.path).path, {})
            payload = body.encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, format: str, *args: object) -> None:
            return

    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"ready http://127.0.0.1:{port}/", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


def _landing_page(scenarios: Sequence[Mapping[str, Any]]) -> str:
    options = "".join(
        f'<option value="{escape(str(item["question"]))}">{escape(str(item["label"]))}</option>'
        for item in scenarios
    )
    return _page(
        "Financial Insight Agent",
        f"""
<main><p class="eyebrow">Evidence-based financial research</p>
<h1>근거 기반 기업분석</h1>
<p>질문을 지원 intent에 연결하고 citation-bound observation만 표시합니다.</p>
<form method="get" action="/analysis">
<label>기업
<select name="company_id">
<option value="{SUPPORTED_COMPANY_ID}">엔씨소프트</option>
</select></label>
<label>질문<select name="question">{options}</select></label>
<button type="submit">분석 보기</button></form>
<p class="boundary">recorded replay · live 실행 아님 · 법률 또는 투자 자문 아님</p></main>""",
    )


def _result_page(result: Mapping[str, Any]) -> str:
    if result.get("status") != "ready":
        return _error_page(str(result.get("reason_code", "blocked_by_guard")))
    observations = "".join(
        f"<article><h3>{escape(str(item['title']))}</h3><p>{escape(str(item['text']))}</p></article>"
        for item in result["answer_summary"]["observations"]
    )
    sections = "".join(_section_html(section) for section in result["sections"])
    return _page(
        "분석 결과",
        f"""<main><p class="eyebrow">{escape(str(result["intent"]))}</p><h1>질문별 근거 결과</h1>
<section><h2>핵심 관찰</h2>{observations}</section>{sections}
<section><h2>실행 경계</h2><p>provider 0 · network 0 · model 0 · write 0</p></section></main>""",
    )


def _section_html(section: Mapping[str, Any]) -> str:
    claims = "".join(
        "<li><p>"
        + escape(str(claim["text"]))
        + "</p><code>"
        + escape(str(claim["citation_id"]))
        + "</code><br><code>"
        + escape(json.dumps(claim["locator"]["value"], ensure_ascii=False, sort_keys=True))
        + "</code></li>"
        for claim in section["claims"]
    )
    return f"<section><h2>{escape(str(section['axis']))}</h2><ol>{claims}</ol></section>"


def _error_page(reason: str) -> str:
    return _page(
        "요청 차단", f"<main><h1>blocked_by_guard</h1><code>{escape(reason)}</code></main>"
    )


def _page(title: str, body: str) -> str:
    return (
        """<!doctype html><html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>"""
        + escape(title)
        + """</title><style>
:root{font-family:system-ui,sans-serif;color:#18211d;background:#edf2ee}
body{margin:0}
main{max-width:960px;margin:3rem auto;padding:0 1rem}
section,form{background:white;border:1px solid #cad5cd;border-radius:14px;
padding:1.2rem;margin:1rem 0}
label{display:block;margin:.8rem 0}
select,button{font:inherit;padding:.65rem;width:100%;margin-top:.35rem}
button{background:#163f31;color:white;border:0;border-radius:8px}
.eyebrow{color:#356a58;text-transform:uppercase;letter-spacing:.08em}
.boundary,code{font-size:.82rem;overflow-wrap:anywhere}
ol{padding-left:1.2rem}
article{border-left:3px solid #75a58f;padding-left:1rem}
</style></head><body>"""
        + body
        + "</body></html>"
    )
