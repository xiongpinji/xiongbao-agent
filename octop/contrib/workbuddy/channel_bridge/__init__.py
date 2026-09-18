# SPDX-License-Identifier: MIT
"""Channel inbound → Goal / Task bridge (remote control gate)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from ..task import TaskStore


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class BridgeResult:
    ok: bool
    action: str
    task_id: str = ""
    detail: dict[str, Any] | None = None
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "action": self.action,
            "task_id": self.task_id,
            "detail": self.detail or {},
            "error": self.error,
        }


class ChannelBridge:
    """Map inbound IM messages to local Task create / append with safety gate.

    Gate: ``WB_CHANNEL_BRIDGE=1`` or ``allow=True`` for tests.
    """

    def __init__(
        self,
        task_store: TaskStore,
        *,
        allow: bool = False,
        audit_emit: Callable[..., Any] | None = None,
    ) -> None:
        self.task_store = task_store
        self.allow = allow
        self.audit_emit = audit_emit

    def _gated(self) -> bool:
        if self.allow:
            return True
        import os

        return (os.environ.get("WB_CHANNEL_BRIDGE") or "").strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }

    def handle_inbound(
        self,
        provider: str,
        text: str,
        *,
        sender: str = "",
        mode: str = "craft",
    ) -> BridgeResult:
        if not self._gated():
            return BridgeResult(
                ok=False,
                action="reject",
                error="channel bridge disabled — set WB_CHANNEL_BRIDGE=1",
            )
        text = (text or "").strip()
        if not text:
            return BridgeResult(ok=False, action="reject", error="empty message")

        # Commands: /task <title> | /append <task_id> <text> | free text → new task
        lower = text.lower()
        try:
            if lower.startswith("/task "):
                title = text[6:].strip() or f"from-{provider}"
                rec = self.task_store.create(title, mode=mode, prompt=title)
                result = BridgeResult(True, "create_task", rec.task_id, {"title": title})
            elif lower.startswith("/append "):
                rest = text[8:].strip()
                parts = rest.split(None, 1)
                if len(parts) < 2:
                    return BridgeResult(False, "reject", error="usage: /append <task_id> <text>")
                tid, body = parts[0], parts[1]
                rec = self.task_store.append_message(tid, "user", body)
                result = BridgeResult(True, "append", rec.task_id, {"chars": len(body)})
            else:
                title = f"[{provider}] {text[:40]}"
                rec = self.task_store.create(title, mode=mode, prompt=text, meta={"sender": sender})
                result = BridgeResult(True, "create_task", rec.task_id, {"title": title})
        except Exception as exc:  # noqa: BLE001
            return BridgeResult(False, "error", error=str(exc)[:300])

        if self.audit_emit:
            try:
                self.audit_emit(
                    "channel_bridge",
                    provider=provider,
                    action=result.action,
                    task_id=result.task_id,
                    ok=result.ok,
                )
            except Exception:
                pass
        return result

    def process_inbox_file(self, inbox_path: Path | str, *, limit: int = 50) -> list[dict[str, Any]]:
        path = Path(inbox_path)
        if not path.is_file():
            return []
        results: list[dict[str, Any]] = []
        lines = path.read_text(encoding="utf-8").splitlines()[-limit:]
        for line in lines:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            provider = str(row.get("provider") or "unknown")
            text = str(row.get("text") or row.get("content") or "")
            sender = str(row.get("sender") or "")
            results.append(self.handle_inbound(provider, text, sender=sender).to_dict())
        return results
