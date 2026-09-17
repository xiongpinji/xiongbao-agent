# SPDX-License-Identifier: MIT
"""Routine engine models — persistable scheduled workflows from approved skills."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal


def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class CronSpec:
    """Simple cron-like schedule (string form; APScheduler can consume later)."""

    expr: str  # e.g. "0 9 * * *"
    timezone: str = "Asia/Shanghai"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CronSpec:
        return cls(
            expr=str(data.get("expr") or data.get("cron") or "0 9 * * *"),
            timezone=str(data.get("timezone") or "Asia/Shanghai"),
        )


@dataclass
class EventSpec:
    kind: str  # manual | on_message | webhook
    filter: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EventSpec:
        return cls(kind=str(data.get("kind") or "manual"), filter=str(data.get("filter") or ""))


@dataclass
class RunRecord:
    run_id: str
    started_at: str
    finished_at: str | None = None
    ok: bool = False
    skipped_approvals: list[str] = field(default_factory=list)
    step_results: list[dict[str, Any]] = field(default_factory=list)
    error: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RunRecord:
        return cls(
            run_id=str(data["run_id"]),
            started_at=str(data["started_at"]),
            finished_at=data.get("finished_at"),
            ok=bool(data.get("ok")),
            skipped_approvals=list(data.get("skipped_approvals") or []),
            step_results=list(data.get("step_results") or []),
            error=str(data.get("error") or ""),
        )


@dataclass
class Routine:
    id: str
    bot_id: str
    skill_name: str
    schedule: CronSpec | None = None
    event: EventSpec | None = None
    timezone: str = "Asia/Shanghai"
    enabled: bool = True
    created_at: str = field(default_factory=_utc_iso)
    last_runs: list[RunRecord] = field(default_factory=list)
    max_routines_per_bot: int = 50
    keep_runs: int = 20

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "bot_id": self.bot_id,
            "skill_name": self.skill_name,
            "schedule": self.schedule.to_dict() if self.schedule else None,
            "event": self.event.to_dict() if self.event else None,
            "timezone": self.timezone,
            "enabled": self.enabled,
            "created_at": self.created_at,
            "last_runs": [r.to_dict() for r in self.last_runs[-self.keep_runs :]],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Routine:
        sched = data.get("schedule")
        ev = data.get("event")
        return cls(
            id=str(data["id"]),
            bot_id=str(data.get("bot_id") or "default"),
            skill_name=str(data["skill_name"]),
            schedule=CronSpec.from_dict(sched) if sched else None,
            event=EventSpec.from_dict(ev) if ev else None,
            timezone=str(data.get("timezone") or "Asia/Shanghai"),
            enabled=bool(data.get("enabled", True)),
            created_at=str(data.get("created_at") or _utc_iso()),
            last_runs=[RunRecord.from_dict(r) for r in (data.get("last_runs") or [])],
        )


RunMode = Literal["dry", "test", "live"]
