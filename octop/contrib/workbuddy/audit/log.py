# SPDX-License-Identifier: MIT
"""Append-only JSONL audit trail for Team / Goal / Connector actions."""

from __future__ import annotations

import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


class AuditLog:
    def __init__(self, path: Path | str | None = None) -> None:
        default = os.environ.get("WB_AUDIT_LOG") or ""
        self.path = Path(path or default or "artifacts/audit/workbuddy.jsonl")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def emit(self, action: str, **fields: Any) -> dict[str, Any]:
        record = {
            "ts": _utc(),
            "action": action,
            **fields,
        }
        line = json.dumps(record, ensure_ascii=False)
        with self._lock:
            with self.path.open("a", encoding="utf-8") as fh:
                fh.write(line + "\n")
        return record

    def read_tail(self, n: int = 20) -> list[dict[str, Any]]:
        if not self.path.is_file():
            return []
        lines = self.path.read_text(encoding="utf-8").splitlines()
        out: list[dict[str, Any]] = []
        for line in lines[-n:]:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return out


_default: AuditLog | None = None


def get_audit_log() -> AuditLog:
    global _default
    if _default is None:
        _default = AuditLog()
    return _default
