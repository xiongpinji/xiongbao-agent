# SPDX-License-Identifier: MIT
"""WorkBuddy Console v2 — tasks / skills / connectors / harbor / runtime tabs + APIs."""

from __future__ import annotations

import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .connectors import probe_status as connectors_probe
from .hub import hub_status
from .skills import SkillCatalog
from .task import TaskStore

_STATIC = Path(__file__).resolve().parent / "console" / "index.html"
_API_GET = {
    "/api/status",
    "/api/hub",
    "/api/tasks",
    "/api/skills",
    "/api/connectors",
    "/api/harbor",
    "/api/runtime",
}


def _tasks_root() -> Path:
    return Path("artifacts/tasks")


def api_payload(path: str) -> dict:
    if path in {"/api/status", "/api/hub"}:
        return hub_status()
    if path == "/api/tasks":
        store = TaskStore(_tasks_root())
        rows = [
            {
                "task_id": t.task_id,
                "title": t.title,
                "status": t.status,
                "mode": t.mode,
                "updated_at": t.updated_at,
            }
            for t in store.list_tasks()
        ]
        return {"ok": True, "count": len(rows), "tasks": rows}
    if path == "/api/skills":
        cat = SkillCatalog()
        n = cat.scan()
        items = [
            {
                "id": m.id,
                "name": m.name,
                "description": (m.description_zh or m.description)[:120],
            }
            for m in cat.list()[:40]
        ]
        return {"ok": True, "total": n, "skills": items}
    if path == "/api/connectors":
        return {"ok": True, **connectors_probe()}
    if path == "/api/harbor":
        from .bench.harbor import harbor_status, harness_mount_probe

        return {
            "ok": True,
            "status": harbor_status().to_dict(),
            "harness": harness_mount_probe(),
        }
    if path == "/api/runtime":
        data = hub_status()
        return {
            "ok": True,
            "v": data.get("v"),
            "runtime": data.get("runtime"),
            "tasks": data.get("tasks"),
            "hint": "POST /api/runtime/run-task?task_id=...&dry=1",
        }
    return {"ok": False, "error": "not found"}


def api_post(path: str, query: dict[str, list[str]]) -> dict:
    if path == "/api/runtime/run-task":
        from .runtime import run_task

        tid = (query.get("task_id") or [""])[0].strip()
        if not tid:
            return {"ok": False, "error": "task_id required"}
        dry = (query.get("dry") or ["1"])[0] not in {"0", "false", "no"}
        result = run_task(tid, dry_run=dry)
        return {"ok": result.ok, **result.to_dict()}
    return {"ok": False, "error": "not found"}


class _Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt: str, *args: object) -> None:  # noqa: A003
        return

    def _send(self, code: int, body: bytes, content_type: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self) -> None:  # noqa: N802
        self._send(204, b"", "text/plain")

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path
        if path.startswith("/api/"):
            payload = api_payload(path)
            code = 200 if path in _API_GET else 404
            if path not in _API_GET:
                payload = {"ok": False, "error": "not found"}
            body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
            self._send(code, body, "application/json; charset=utf-8")
            return
        if path in {"/", "/index.html"}:
            if not _STATIC.is_file():
                self._send(404, b"console missing", "text/plain; charset=utf-8")
                return
            self._send(200, _STATIC.read_bytes(), "text/html; charset=utf-8")
            return
        self._send(404, b"not found", "text/plain; charset=utf-8")

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)
        if path.startswith("/api/"):
            payload = api_post(path, query)
            code = 200 if payload.get("ok") or "error" in payload else 404
            if path != "/api/runtime/run-task":
                code = 404
                payload = {"ok": False, "error": "not found"}
            body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
            self._send(code, body, "application/json; charset=utf-8")
            return
        self._send(404, b"not found", "text/plain; charset=utf-8")


def serve(*, host: str = "127.0.0.1", port: int = 8010) -> None:
    httpd = ThreadingHTTPServer((host, port), _Handler)
    print(
        f"[wb-console] http://{host}:{port}/  "
        "APIs: /api/status|/api/tasks|/api/skills|/api/connectors|/api/harbor|/api/runtime"
    )
    httpd.serve_forever()


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="console_server")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8010)
    args = p.parse_args(argv)
    serve(host=args.host, port=args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
