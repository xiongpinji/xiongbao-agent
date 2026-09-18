# SPDX-License-Identifier: MIT
"""Task lifecycle — WorkBuddy create-task / task-management / conversation / results."""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

TASK_STATUSES = ("pending", "running", "waiting", "completed", "failed", "cancelled")


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_id(raw: str) -> str:
    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in raw.strip())
    if not safe:
        raise ValueError("empty task id")
    return safe


@dataclass
class TaskMessage:
    role: str  # user | assistant | system
    content: str
    ts: str = field(default_factory=_utc)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class TaskRecord:
    task_id: str
    title: str
    status: str
    created_at: str
    updated_at: str
    mode: str = "craft"  # ask | plan | craft
    project_id: str = ""
    goal_run_id: str = ""
    messages: list[TaskMessage] = field(default_factory=list)
    results: list[dict[str, Any]] = field(default_factory=list)
    meta: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "title": self.title,
            "status": self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "mode": self.mode,
            "project_id": self.project_id,
            "goal_run_id": self.goal_run_id,
            "messages": [m.to_dict() for m in self.messages],
            "results": list(self.results),
            "meta": dict(self.meta),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TaskRecord:
        msgs = [
            TaskMessage(
                role=str(m.get("role") or "user"),
                content=str(m.get("content") or ""),
                ts=str(m.get("ts") or ""),
            )
            for m in (data.get("messages") or [])
            if isinstance(m, dict)
        ]
        return cls(
            task_id=str(data["task_id"]),
            title=str(data.get("title") or data["task_id"]),
            status=str(data.get("status") or "pending"),
            created_at=str(data.get("created_at") or ""),
            updated_at=str(data.get("updated_at") or ""),
            mode=str(data.get("mode") or "craft"),
            project_id=str(data.get("project_id") or ""),
            goal_run_id=str(data.get("goal_run_id") or ""),
            messages=msgs,
            results=list(data.get("results") or []),
            meta=dict(data.get("meta") or {}),
        )


class TaskStore:
    """Filesystem-backed task store under ``<root>/<task_id>/task.json``."""

    def __init__(self, root: Path | str) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _dir(self, task_id: str) -> Path:
        return self.root / _safe_id(task_id)

    def _path(self, task_id: str) -> Path:
        return self._dir(task_id) / "task.json"

    def create(
        self,
        title: str,
        *,
        task_id: str | None = None,
        mode: str = "craft",
        project_id: str = "",
        prompt: str = "",
        meta: dict[str, Any] | None = None,
    ) -> TaskRecord:
        tid = _safe_id(task_id or f"t-{uuid.uuid4().hex[:10]}")
        if self._path(tid).is_file():
            raise FileExistsError(f"task already exists: {tid}")
        now = _utc()
        record = TaskRecord(
            task_id=tid,
            title=title.strip() or tid,
            status="pending",
            created_at=now,
            updated_at=now,
            mode=mode,
            project_id=project_id,
            meta=dict(meta or {}),
        )
        if prompt.strip():
            record.messages.append(TaskMessage(role="user", content=prompt.strip()))
        self._save(record)
        try:
            from ..audit import audit_task

            audit_task(record, action="task.create")
        except Exception:
            pass
        return record

    def _save(self, record: TaskRecord) -> Path:
        d = self._dir(record.task_id)
        d.mkdir(parents=True, exist_ok=True)
        path = d / "task.json"
        path.write_text(
            json.dumps(record.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return path

    def get(self, task_id: str) -> TaskRecord:
        path = self._path(task_id)
        if not path.is_file():
            raise FileNotFoundError(f"task not found: {task_id}")
        data = json.loads(path.read_text(encoding="utf-8"))
        return TaskRecord.from_dict(data)

    def set_status(self, task_id: str, status: str) -> TaskRecord:
        if status not in TASK_STATUSES:
            raise ValueError(f"invalid status: {status}; expected one of {TASK_STATUSES}")
        rec = self.get(task_id)
        rec.status = status
        rec.updated_at = _utc()
        self._save(rec)
        return rec

    def append_message(self, task_id: str, role: str, content: str) -> TaskRecord:
        rec = self.get(task_id)
        rec.messages.append(TaskMessage(role=role, content=content))
        if rec.status == "pending":
            rec.status = "running"
        rec.updated_at = _utc()
        self._save(rec)
        return rec

    def add_result(self, task_id: str, result: dict[str, Any]) -> TaskRecord:
        rec = self.get(task_id)
        payload = dict(result)
        payload.setdefault("ts", _utc())
        rec.results.append(payload)
        rec.updated_at = _utc()
        self._save(rec)
        return rec

    def complete(self, task_id: str, *, summary: str = "", ok: bool = True) -> TaskRecord:
        rec = self.get(task_id)
        if summary:
            rec.results.append({"kind": "summary", "text": summary, "ts": _utc()})
        rec.status = "completed" if ok else "failed"
        rec.updated_at = _utc()
        self._save(rec)
        return rec

    def link_goal(self, task_id: str, goal_run_id: str) -> TaskRecord:
        rec = self.get(task_id)
        rec.goal_run_id = goal_run_id
        rec.updated_at = _utc()
        self._save(rec)
        return rec

    def update(
        self,
        task_id: str,
        *,
        title: str | None = None,
        mode: str | None = None,
        status: str | None = None,
        meta_patch: dict[str, Any] | None = None,
    ) -> TaskRecord:
        rec = self.get(task_id)
        if title is not None:
            rec.title = title.strip() or rec.title
        if mode is not None:
            rec.mode = mode.strip() or rec.mode
        if status is not None:
            if status not in TASK_STATUSES:
                raise ValueError(f"invalid status: {status}")
            rec.status = status
        if meta_patch:
            rec.meta.update(meta_patch)
        rec.updated_at = _utc()
        self._save(rec)
        return rec

    def list_tasks(
        self,
        *,
        status: str | None = None,
        query: str | None = None,
        include_archived: bool = False,
    ) -> list[TaskRecord]:
        rows: list[TaskRecord] = []
        if not self.root.is_dir():
            return rows
        q = (query or "").strip().lower()
        for p in sorted(self.root.iterdir(), key=lambda x: x.name, reverse=True):
            if not (p / "task.json").is_file():
                continue
            rec = self.get(p.name)
            archived = bool(rec.meta.get("archived"))
            if archived and not include_archived:
                continue
            if status is not None and rec.status != status:
                continue
            if q and q not in rec.title.lower() and q not in rec.task_id.lower():
                continue
            rows.append(rec)
        # pinned first
        rows.sort(
            key=lambda r: (0 if r.meta.get("pinned") else 1, r.updated_at or ""),
            reverse=False,
        )
        pinned = [r for r in rows if r.meta.get("pinned")]
        rest = [r for r in rows if not r.meta.get("pinned")]
        rest.sort(key=lambda r: r.updated_at or "", reverse=True)
        return pinned + rest
