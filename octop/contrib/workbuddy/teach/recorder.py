# SPDX-License-Identifier: MIT
"""Teach session recorder — append-only step capture (V2 MVP).

CDP/IM listeners can feed ``append_*`` later; this layer stays stdlib-only.
"""

from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path

from .models import HIGH_RISK_KINDS, HIGH_RISK_TOOLS, RecordedStep, StepKind, TeachRecording


def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _slug(text: str, *, fallback: str = "skill") -> str:
    s = re.sub(r"[^a-zA-Z0-9\u4e00-\u9fff]+", "-", text.strip().lower())
    s = re.sub(r"-{2,}", "-", s).strip("-")
    return (s[:48] or fallback)


class TeachRecorder:
    """In-memory teach session with optional JSONL persistence."""

    def __init__(
        self,
        *,
        bot_id: str = "default",
        intent: str = "",
        store_dir: Path | None = None,
        max_duration_sec: int = 600,
        recording_id: str | None = None,
    ) -> None:
        self.store_dir = Path(store_dir) if store_dir else None
        rid = recording_id or uuid.uuid4().hex[:12]
        self.recording = TeachRecording(
            id=rid,
            bot_id=bot_id,
            intent=intent,
            max_duration_sec=max_duration_sec,
        )
        if self.store_dir:
            self.store_dir.mkdir(parents=True, exist_ok=True)
            self._jsonl_path().write_text("", encoding="utf-8")

    def _jsonl_path(self) -> Path:
        assert self.store_dir is not None
        return self.store_dir / f"{self.recording.id}.jsonl"

    def _snapshot_path(self) -> Path:
        assert self.store_dir is not None
        return self.store_dir / f"{self.recording.id}.json"

    def _assert_open(self) -> None:
        if self.recording.status != "recording":
            raise RuntimeError(f"recording {self.recording.id} is {self.recording.status}")

    def _elapsed_ok(self) -> bool:
        try:
            start = datetime.fromisoformat(self.recording.created_at)
            now = datetime.now(timezone.utc)
            if start.tzinfo is None:
                start = start.replace(tzinfo=timezone.utc)
            return (now - start).total_seconds() <= self.recording.max_duration_sec
        except ValueError:
            return True

    def append(
        self,
        kind: StepKind,
        summary: str,
        *,
        target: str = "",
        value: str = "",
        tool_name: str = "",
        meta: dict | None = None,
    ) -> RecordedStep:
        self._assert_open()
        if not self._elapsed_ok():
            raise TimeoutError(
                f"teach session exceeded {self.recording.max_duration_sec}s "
                "(Grok Bot–aligned 10 min cap)"
            )
        # Tag high-risk; do not execute side effects here (executor layer enforces)
        tool_l = (tool_name or summary).lower()
        meta_out = dict(meta or {})
        if any(t in tool_l for t in HIGH_RISK_TOOLS) or kind in HIGH_RISK_KINDS:
            meta_out["high_risk"] = True
            meta_out["approval_required"] = True
        step = RecordedStep(
            index=len(self.recording.steps),
            kind=kind,
            summary=summary,
            target=target,
            value=value,
            tool_name=tool_name,
            meta=meta_out,
        )
        self.recording.steps.append(step)
        if self.store_dir:
            with self._jsonl_path().open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(step.to_dict(), ensure_ascii=False) + "\n")
        return step

    def navigate(self, url: str, summary: str | None = None) -> RecordedStep:
        return self.append("navigate", summary or f"打开 {url}", target=url)

    def click(self, selector: str, summary: str | None = None) -> RecordedStep:
        return self.append("click", summary or f"点击 {selector}", target=selector)

    def type_text(self, selector: str, text: str, summary: str | None = None) -> RecordedStep:
        return self.append(
            "type",
            summary or f"在 {selector} 输入",
            target=selector,
            value=text,
        )

    def read_data(self, source: str, summary: str | None = None) -> RecordedStep:
        return self.append("read", summary or f"读取 {source}", target=source)

    def decision(self, question: str) -> RecordedStep:
        return self.append("decision", question)

    def close(self) -> TeachRecording:
        self._assert_open()
        self.recording.closed_at = _utc_iso()
        self.recording.status = "closed"
        if self.store_dir:
            self._snapshot_path().write_text(
                json.dumps(self.recording.to_dict(), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        return self.recording

    @staticmethod
    def suggested_skill_name(intent: str) -> str:
        return _slug(intent, fallback="taught-skill")
