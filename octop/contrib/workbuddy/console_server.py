# SPDX-License-Identifier: MIT
"""WorkBuddy Console v11 — multi-tenant auth + scoped task APIs."""

from __future__ import annotations

import argparse
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from .connectors import probe_status as connectors_probe
from .hub import hub_status
from .skills import SkillCatalog
from .task import TaskStore
from .tenant import (
    TenantContext,
    TenantRegistry,
    TenantRoots,
    auth_required,
    exchange_casdoor_token,
    issue_token,
    parse_bearer,
    verify_token,
)

_STATIC = Path(__file__).resolve().parent / "console" / "index.html"
_PUBLIC_GET = {"/api/health"}
_API_GET = {
    "/api/health",
    "/api/status",
    "/api/hub",
    "/api/tasks",
    "/api/skills",
    "/api/connectors",
    "/api/harbor",
    "/api/runtime",
    "/api/tenant",
}


def _registry() -> TenantRegistry:
    return TenantRegistry(os.environ.get("WB_TENANT_REGISTRY") or "artifacts/tenants/_registry.json")


def _tasks_root_for(ctx: TenantContext | None) -> Path:
    if ctx is not None:
        roots = TenantRoots(ctx.tenant_id, ctx.user_id)
        roots.ensure()
        return roots.tasks
    return Path("artifacts/tasks")


def api_payload(path: str, ctx: TenantContext | None) -> dict[str, Any]:
    if path == "/api/health":
        return {"ok": True, "auth_required": auth_required(), "v": 11}
    if path in {"/api/status", "/api/hub"}:
        data = hub_status()
        if ctx is not None:
            data["tenant"] = ctx.to_claims()
            data["tasks"] = {
                "root": str(_tasks_root_for(ctx)),
                "count": sum(
                    1 for p in _tasks_root_for(ctx).iterdir() if (p / "task.json").is_file()
                )
                if _tasks_root_for(ctx).is_dir()
                else 0,
            }
        return data
    if path == "/api/tenant":
        if ctx is None:
            return {"ok": False, "error": "unauthorized"}
        rec = _registry().get(ctx.tenant_id)
        if rec is None:
            return {"ok": False, "error": "tenant not found"}
        return {
            "ok": True,
            "tenant_id": rec.tenant_id,
            "name": rec.name,
            "role": ctx.role,
            "quota": rec.quota.to_dict(),
            "roots": TenantRoots(ctx.tenant_id, ctx.user_id).to_dict(),
        }
    if path == "/api/tasks":
        store = TaskStore(_tasks_root_for(ctx))
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


def api_post(path: str, query: dict[str, list[str]], body: dict[str, Any], ctx: TenantContext | None) -> dict[str, Any]:
    if path == "/api/auth/login":
        tid = str(body.get("tenant_id") or (query.get("tenant_id") or [""])[0]).strip()
        uid = str(body.get("user_id") or (query.get("user_id") or [""])[0]).strip()
        key = str(body.get("api_key") or (query.get("api_key") or [""])[0]).strip()
        casdoor = str(body.get("casdoor_token") or "").strip()
        try:
            if casdoor:
                new_ctx = exchange_casdoor_token(casdoor)
            else:
                new_ctx = _registry().authenticate(tid, uid, key)
            token = issue_token(new_ctx)
            return {"ok": True, "token": token, "claims": new_ctx.to_claims()}
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": str(exc)}
    if path == "/api/runtime/run-task":
        from .runtime import run_task

        tid = (query.get("task_id") or [body.get("task_id", "")])[0]
        tid = str(tid).strip()
        if not tid:
            return {"ok": False, "error": "task_id required"}
        dry = (query.get("dry") or ["1"])[0] not in {"0", "false", "no"}
        result = run_task(tid, dry_run=dry, tasks_root=_tasks_root_for(ctx))
        return {"ok": result.ok, **result.to_dict()}
    return {"ok": False, "error": "not found"}


def _read_json_body(handler: BaseHTTPRequestHandler) -> dict[str, Any]:
    length = int(handler.headers.get("Content-Length") or 0)
    if length <= 0:
        return {}
    raw = handler.rfile.read(length)
    try:
        data = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


class _Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt: str, *args: object) -> None:  # noqa: A003
        return

    def _send(self, code: int, body: bytes, content_type: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _auth_context(self) -> tuple[TenantContext | None, dict[str, Any] | None]:
        """Return (ctx, error_payload). error_payload set → respond 401."""
        if not auth_required():
            # Optional bearer still accepted for scoped roots
            token = parse_bearer(self.headers.get("Authorization"))
            if token:
                try:
                    return verify_token(token), None
                except ValueError as exc:
                    return None, {"ok": False, "error": str(exc)}
            return None, None
        path = urlparse(self.path).path
        if path in _PUBLIC_GET or path == "/api/auth/login":
            return None, None
        token = parse_bearer(self.headers.get("Authorization"))
        if not token:
            return None, {"ok": False, "error": "unauthorized", "hint": "POST /api/auth/login"}
        try:
            return verify_token(token), None
        except ValueError as exc:
            return None, {"ok": False, "error": str(exc)}

    def do_OPTIONS(self) -> None:  # noqa: N802
        self._send(204, b"", "text/plain")

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path
        if path.startswith("/api/"):
            ctx, err = self._auth_context()
            if err is not None:
                body = json.dumps(err, ensure_ascii=False).encode("utf-8")
                self._send(401, body, "application/json; charset=utf-8")
                return
            payload = api_payload(path, ctx)
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
        body_obj = _read_json_body(self)
        if path.startswith("/api/"):
            ctx, err = self._auth_context()
            if err is not None and path != "/api/auth/login":
                body = json.dumps(err, ensure_ascii=False).encode("utf-8")
                self._send(401, body, "application/json; charset=utf-8")
                return
            payload = api_post(path, query, body_obj, ctx)
            if path == "/api/auth/login":
                code = 200 if payload.get("ok") else 401
            elif path == "/api/runtime/run-task":
                code = 200 if payload.get("ok") or "error" in payload else 404
            else:
                code = 404
                payload = {"ok": False, "error": "not found"}
            body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
            self._send(code, body, "application/json; charset=utf-8")
            return
        self._send(404, b"not found", "text/plain; charset=utf-8")


def serve(*, host: str = "127.0.0.1", port: int = 8010) -> None:
    httpd = ThreadingHTTPServer((host, port), _Handler)
    mode = "AUTH ON" if auth_required() else "auth optional"
    print(
        f"[wb-console] http://{host}:{port}/  ({mode})  "
        "APIs: /api/health|/api/auth/login|/api/tasks|/api/tenant|/api/runtime"
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
