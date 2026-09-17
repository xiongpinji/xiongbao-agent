# SPDX-License-Identifier: MIT
"""Tick-based Routine scheduler (stdlib cron; no APScheduler process required).

Intended use::

    # cron host / Task Scheduler / systemd timer every minute:
    python -S -m octop.contrib.workbuddy.teach_cli tick --mode dry
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from ..teach.store import TeachStore
from .cron import is_due, local_now, next_match
from .engine import RoutineEngine
from .models import Routine, RunMode, RunRecord
from .store import RoutineStore


@dataclass
class DueItem:
    routine: Routine
    local_slot: str
    next_after: str | None = None


@dataclass
class TickResult:
    routine_id: str
    skill_name: str
    fired: bool
    run: RunRecord | None = None
    error: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "routine_id": self.routine_id,
            "skill_name": self.skill_name,
            "fired": self.fired,
            "run": self.run.to_dict() if self.run else None,
            "error": self.error,
        }


class RoutineScheduler:
    """Evaluate cron due windows and optionally execute via RoutineEngine."""

    def __init__(
        self,
        routines: RoutineStore,
        teach: TeachStore,
        engine: RoutineEngine | None = None,
    ) -> None:
        self.routines = routines
        self.teach = teach
        self.engine = engine or RoutineEngine(routines)

    def list_due(self, *, now: datetime | None = None) -> list[DueItem]:
        due: list[DueItem] = []
        for rid in self.routines.list_ids():
            routine = self.routines.load(rid)
            if not routine.enabled or not routine.schedule:
                continue
            tz = routine.schedule.timezone or routine.timezone
            if not is_due(
                routine.schedule.expr,
                tz_name=tz,
                last_fired_at=routine.last_fired_at or routine.created_at,
                now=now,
            ):
                continue
            slot = local_now(tz, now=now).isoformat()
            nxt = next_match(routine.schedule.expr, tz_name=tz, after=now)
            due.append(
                DueItem(
                    routine=routine,
                    local_slot=slot,
                    next_after=nxt.isoformat() if nxt else None,
                )
            )
        return due

    def preview(self, *, now: datetime | None = None) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for rid in self.routines.list_ids():
            routine = self.routines.load(rid)
            row: dict[str, Any] = {
                "id": routine.id,
                "skill_name": routine.skill_name,
                "enabled": routine.enabled,
                "cron": routine.schedule.expr if routine.schedule else None,
                "timezone": (routine.schedule.timezone if routine.schedule else None)
                or routine.timezone,
                "last_fired_at": routine.last_fired_at,
                "due": False,
                "next": None,
            }
            if routine.schedule:
                tz = row["timezone"]
                row["due"] = is_due(
                    routine.schedule.expr,
                    tz_name=tz,
                    last_fired_at=routine.last_fired_at or routine.created_at,
                    now=now,
                )
                nxt = next_match(routine.schedule.expr, tz_name=tz, after=now)
                row["next"] = nxt.isoformat() if nxt else None
            rows.append(row)
        return rows

    def tick(
        self,
        *,
        mode: RunMode = "dry",
        now: datetime | None = None,
        approvals: set[str] | None = None,
        confirm_test: bool = False,
        mark_fired_on_failure: bool = True,
    ) -> list[TickResult]:
        """Fire all currently due routines once for this minute slot."""
        results: list[TickResult] = []
        fired_at = (now or datetime.now(timezone.utc)).astimezone(timezone.utc).isoformat()
        for item in self.list_due(now=now):
            routine = item.routine
            tr = TickResult(routine_id=routine.id, skill_name=routine.skill_name, fired=False)
            try:
                draft = self.teach.load_draft(routine.skill_name)
                run = self.engine.run(
                    routine,
                    draft,
                    mode=mode,
                    approvals=approvals,
                    confirm_test=confirm_test,
                    context={"scheduler": True, "slot": item.local_slot},
                )
                # engine.save already appended run; reload & stamp fire time
                routine = self.routines.load(routine.id)
                if run.ok or mark_fired_on_failure:
                    routine.last_fired_at = fired_at
                    self.routines.save(routine)
                tr.fired = True
                tr.run = run
                if not run.ok:
                    tr.error = run.error
            except Exception as exc:  # noqa: BLE001
                tr.error = str(exc)
                if mark_fired_on_failure:
                    try:
                        routine = self.routines.load(routine.id)
                        routine.last_fired_at = fired_at
                        self.routines.save(routine)
                    except Exception:  # noqa: BLE001
                        pass
            results.append(tr)
        return results
