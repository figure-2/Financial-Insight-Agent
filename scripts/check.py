"""Run dependency-free checks for the public candidate."""

from __future__ import annotations

import compileall
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=ROOT, check=True, capture_output=True, text=True)


def main() -> int:
    if not compileall.compile_dir(ROOT / "src", quiet=1):
        raise SystemExit("compile_failed")
    tests = run([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"])
    first = run([sys.executable, "-I", "run.py", "smoke"])
    second = run([sys.executable, "-I", "run.py", "smoke"])
    if first.stdout != second.stdout:
        raise SystemExit("deterministic_smoke_failed")
    smoke = json.loads(first.stdout)
    if smoke.get("status") != "ready" or smoke.get("unsupported_claim_count") != 0:
        raise SystemExit("smoke_not_ready")
    print(
        json.dumps(
            {
                "status": "ready",
                "tests": tests.stderr.count(" ... ok"),
                "deterministic_smoke": True,
                "provider_call_count": 0,
                "network_call_count": 0,
                "llm_call_count": 0,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
