# SPDX-License-Identifier: MIT
"""Ops health snapshot + failure replay helpers for private delivery."""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any

from .console_events import read_events
from .task import TaskStore

_STARTED_AT = time.time()


def process_uptime_s() -> float:
    return round(time.time() - _STARTED_AT, 1)


def health_detail(*, auth_required: bool, model: str | None = None) -> dict[str, Any]:
    return {
        "ok": True,
        "auth_required": auth_required,
        "v": 20,
        "model": model,
        "uptime_s": process_uptime_s(),
        "pid": os.getpid(),
        "artifacts_root": os.environ.get("WB_ARTIFACTS_ROOT") or "artifacts",
        "restart_hint": (
            "docker compose -f deploy/docker-compose.workbuddy.yml "
            "--env-file deploy/.env.workbuddy --profile prod "
            "up -d wb-console-prod --force-recreate"
        ),
    }


def task_replay(task_dir: Path, *, store: TaskStore | None = None, task_id: str = "") -> dict[str, Any]:
    """Assemble a failure/success replay pack: events + last messages + status."""
    rows, cursor = read_events(task_dir, after=0)
    status = ""
    messages: list[dict[str, Any]] = []
    error = ""
    if store is not None and task_id:
        try:
            rec = store.get(task_id)
            status = rec.status
            messages = [{"role": m.role, "content": m.content[:500], "ts": m.ts} for m in rec.messages[-12:]]
            if rec.status == "failed":
                for m in reversed(rec.messages):
                    if m.role in {"assistant", "system"} and m.content:
                        error = m.content[:800]
                        break
        except FileNotFoundError:
            pass
    terminal = next((r for r in reversed(rows) if r.get("terminal") or r.get("kind") in {"failed", "error", "completed", "done"}), None)
    return {
        "ok": True,
        "task_id": task_id,
        "status": status,
        "error": error or (terminal or {}).get("message") or "",
        "events": rows,
        "cursor": cursor,
        "messages": messages,
        "terminal": terminal,
        "event_count": len(rows),
    }


def restart_playbook() -> dict[str, Any]:
    return {
        "ok": True,
        "steps": [
            {
                "id": "health",
                "title": "检查健康",
                "cmd": "curl -fsS http://127.0.0.1:8010/api/health",
            },
            {
                "id": "logs",
                "title": "查看最近日志",
                "cmd": "docker logs --tail 200 deploy-wb-console-prod-1",
            },
            {
                "id": "recreate",
                "title": "重建 console（保留 artifacts 卷）",
                "cmd": (
                    "docker compose -f deploy/docker-compose.workbuddy.yml "
                    "--env-file deploy/.env.workbuddy --profile prod "
                    "up -d wb-console-prod --force-recreate"
                ),
            },
            {
                "id": "verify",
                "title": "复验健康与登录",
                "cmd": "python -S scripts/verify_customer_playbook.py",
            },
        ],
    }
