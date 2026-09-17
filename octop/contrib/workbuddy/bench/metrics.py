# SPDX-License-Identifier: MIT
"""Structured observability for bench runs (JSONL + summary JSON).

Designed so a later SigNoz / OTLP exporter can consume the same events
without changing the runner.
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class RunMetrics:
    """One structured event."""

    event: str
    ts: str = field(default_factory=_utc_now)
    attrs: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {"event": self.event, "ts": self.ts, **self.attrs}


class MetricsSink:
    """Append-only JSONL sink + in-memory buffer."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = Path(path) if path else None
        self.events: list[RunMetrics] = []
        self._t0 = time.perf_counter()
        if self.path:
            self.path.parent.mkdir(parents=True, exist_ok=True)

    def emit(self, event: str, **attrs: Any) -> RunMetrics:
        m = RunMetrics(event=event, attrs=attrs)
        self.events.append(m)
        if self.path:
            with self.path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(m.to_dict(), ensure_ascii=False) + "\n")
        return m

    def elapsed_ms(self) -> float:
        return (time.perf_counter() - self._t0) * 1000.0

    def write_summary(self, path: Path, payload: dict[str, Any]) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
