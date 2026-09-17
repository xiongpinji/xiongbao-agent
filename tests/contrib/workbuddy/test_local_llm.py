# SPDX-License-Identifier: MIT
"""Tests for local LLM probe + OpenAICompatCaller (offline unit + optional live)."""

from __future__ import annotations

import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT))

from octop.contrib.workbuddy.team.llm import OpenAICompatCaller  # noqa: E402
from octop.contrib.workbuddy.team.probe import probe_local_llm  # noqa: E402
from octop.contrib.workbuddy.team.runtime import TeamAgentRuntime  # noqa: E402


class _Handler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args) -> None:  # noqa: A003
        return

    def do_GET(self) -> None:  # noqa: N802
        if self.path.rstrip("/").endswith("/models"):
            body = json.dumps(
                {"data": [{"id": "stub-local:1b"}, {"id": "qwen2.5:1.5b"}]}
            ).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        self.send_response(404)
        self.end_headers()

    def do_POST(self) -> None:  # noqa: N802
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length)
        payload = json.loads(raw.decode("utf-8"))
        msgs = payload.get("messages") or []
        user = next((m["content"] for m in msgs if m.get("role") == "user"), "")
        content = f"## stub reply\n\n针对：{user[:80]}\n\n结论：本地推理通路可用。"
        body = json.dumps(
            {
                "choices": [{"message": {"role": "assistant", "content": content}}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 20},
            }
        ).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def _start_stub() -> tuple[HTTPServer, str]:
    server = HTTPServer(("127.0.0.1", 0), _Handler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, f"http://127.0.0.1:{port}/v1"


def test_probe_and_caller_against_stub() -> None:
    server, base = _start_stub()
    try:
        probe = probe_local_llm([base])
        assert probe.ok, probe.error
        assert "qwen2.5:1.5b" in probe.models or probe.preferred_model
        caller = OpenAICompatCaller(base_url=base, model=probe.preferred_model, max_tokens=128)
        # Minimal fake team definition via StockPartner if present
        expert = (
            PROJECT
            / "octop"
            / "src"
            / "octop"
            / "infra"
            / "agents"
            / "experts"
            / "library"
            / "StockPartnerTeam"
        )
        assert expert.is_dir(), expert
        rt = TeamAgentRuntime.from_expert_dir(expert, caller=caller, materialize=True)
        rt.definition.members = rt.definition.members[:1]
        for phase in rt.definition.phases:
            object.__setattr__(phase, "member_ids", (rt.definition.members[0].agent_id,))
        result = rt.run_sync("测试本地模型通路", dry_run=False)
        assert len(result.member_outputs) == 1
        assert len(result.final_report) >= 20
        assert caller.stats.calls >= 2
        assert caller.stats.errors == 0
    finally:
        server.shutdown()


def test_probe_real_ollama_optional() -> None:
    probe = probe_local_llm()
    if not probe.ok:
        print("SKIP live ollama (not reachable)")
        return
    assert probe.preferred_model
    print(f"OK live probe {probe.base_url} model={probe.preferred_model}")


def main() -> int:
    failed = 0
    for fn in (test_probe_and_caller_against_stub, test_probe_real_ollama_optional):
        try:
            fn()
            print(f"OK  {fn.__name__}")
        except Exception as exc:  # noqa: BLE001
            failed += 1
            print(f"FAIL {fn.__name__}: {exc}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
