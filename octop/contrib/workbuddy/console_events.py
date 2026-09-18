# SPDX-License-Identifier: MIT
"""Task run event log + SSE framing for console parity."""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterator


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def events_path(task_dir: Path) -> Path:
    return Path(task_dir) / "run_events.jsonl"


def clear_events(task_dir: Path) -> None:
    path = events_path(task_dir)
    if path.is_file():
        path.unlink()


def append_event(task_dir: Path, event: dict[str, Any]) -> dict[str, Any]:
    path = events_path(task_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    row = dict(event)
    row.setdefault("ts", _utc())
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    return row


def make_emitter(task_dir: Path) -> Callable[[dict[str, Any]], None]:
    def _emit(event: dict[str, Any]) -> None:
        append_event(task_dir, event)

    return _emit


def read_events(task_dir: Path, *, after: int = 0) -> tuple[list[dict[str, Any]], int]:
    path = events_path(task_dir)
    if not path.is_file():
        return [], after
    rows: list[dict[str, Any]] = []
    idx = 0
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            if idx >= after:
                try:
                    data = json.loads(line)
                except json.JSONDecodeError:
                    data = {"kind": "raw", "text": line}
                if isinstance(data, dict):
                    data["_i"] = idx
                    rows.append(data)
            idx += 1
    return rows, idx


def iter_sse_frames(
    task_dir: Path,
    *,
    after: int = 0,
    timeout_s: float = 120.0,
    poll_s: float = 0.35,
) -> Iterator[bytes]:
    """Yield SSE frames until a terminal event or timeout."""
    start = time.monotonic()
    cursor = after
    terminal = {"done", "failed", "error", "accepted", "completed"}
    yield b": workbuddy-events\n\n"
    while time.monotonic() - start < timeout_s:
        rows, cursor = read_events(task_dir, after=cursor)
        for row in rows:
            payload = json.dumps(row, ensure_ascii=False)
            chunk = f"id: {row.get('_i', 0)}\nevent: {row.get('kind', 'message')}\ndata: {payload}\n\n"
            yield chunk.encode("utf-8")
            kind = str(row.get("kind") or "")
            if kind in terminal or row.get("terminal"):
                return
        time.sleep(poll_s)
    # timeout heartbeat end
    end = json.dumps({"kind": "timeout", "terminal": True, "ts": _utc()}, ensure_ascii=False)
    yield f"event: timeout\ndata: {end}\n\n".encode("utf-8")
