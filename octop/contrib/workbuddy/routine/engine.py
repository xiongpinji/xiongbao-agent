# SPDX-License-Identifier: MIT
"""RoutineEngine — run approved SkillDraft steps with safety gates."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Protocol

from ..teach.models import DraftStep, SkillDraft
from .models import CronSpec, EventSpec, Routine, RunMode, RunRecord
from .safety import SafetyError, assert_draft_approved, assert_no_stale_reuse, pending_approvals
from .store import RoutineStore


def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class StepRunner(Protocol):
    def __call__(self, step: DraftStep, *, context: dict[str, Any]) -> dict[str, Any]: ...


class MockStepRunner:
    """Deterministic runner for tests / dry demos."""

    def __call__(self, step: DraftStep, *, context: dict[str, Any]) -> dict[str, Any]:
        return {
            "index": step.index,
            "kind": step.kind,
            "ok": True,
            "output": f"[mock] {step.instruction}",
        }


class RoutineEngine:
    def __init__(
        self,
        store: RoutineStore,
        *,
        runner: StepRunner | None = None,
        max_per_bot: int = 50,
    ) -> None:
        self.store = store
        self.runner: StepRunner = runner or MockStepRunner()
        self.max_per_bot = max_per_bot

    def create_from_draft(
        self,
        draft: SkillDraft,
        *,
        bot_id: str = "default",
        cron: str | None = "0 9 * * *",
        timezone: str = "Asia/Shanghai",
        routine_id: str | None = None,
        enabled: bool = True,
    ) -> Routine:
        assert_draft_approved(draft)
        assert_no_stale_reuse(draft.stale_data_policy)
        if self.store.count_for_bot(bot_id) >= self.max_per_bot:
            raise SafetyError(f"bot {bot_id} already has {self.max_per_bot} routines")
        rid = routine_id or f"rt-{draft.name}-{uuid.uuid4().hex[:6]}"
        routine = Routine(
            id=rid,
            bot_id=bot_id,
            skill_name=draft.name,
            schedule=CronSpec(expr=cron, timezone=timezone) if cron else None,
            event=EventSpec(kind="manual") if not cron else None,
            timezone=timezone,
            enabled=enabled,
        )
        self.store.save(routine)
        return routine

    def run(
        self,
        routine: Routine,
        draft: SkillDraft,
        *,
        mode: RunMode = "dry",
        approvals: set[str] | None = None,
        context: dict[str, Any] | None = None,
        confirm_test: bool = False,
    ) -> RunRecord:
        """Execute routine steps.

        - dry: simulate, no side effects assumed
        - test/live: real runner path; test requires confirm_test=True (Grok-aligned)
        """
        if draft.name != routine.skill_name:
            raise SafetyError("draft name mismatch with routine.skill_name")
        assert_draft_approved(draft)
        assert_no_stale_reuse(draft.stale_data_policy)
        if not routine.enabled and mode != "dry":
            raise SafetyError("routine disabled")

        if mode == "test" and not confirm_test:
            raise SafetyError("test run requires confirm_test=True (real execution)")

        granted = set(approvals or set())
        if mode == "dry":
            # dry auto-grants for simulation visibility but records them
            for step in draft.steps:
                if step.requires_approval:
                    granted.add(f"step:{step.index}")
            for ap in draft.approvals:
                granted.add(f"action:{ap.action}")

        missing = pending_approvals(draft, granted)
        if missing and mode != "dry":
            raise SafetyError(f"missing approvals: {', '.join(missing)}")

        run = RunRecord(
            run_id=uuid.uuid4().hex[:10],
            started_at=_utc_iso(),
            skipped_approvals=list(missing) if mode == "dry" else [],
        )
        ctx = dict(context or {})
        ctx["mode"] = mode
        ctx["routine_id"] = routine.id

        try:
            for step in draft.steps:
                if mode == "dry":
                    result = {
                        "index": step.index,
                        "kind": step.kind,
                        "ok": True,
                        "output": f"[dry] {step.instruction}",
                        "requires_approval": step.requires_approval,
                    }
                else:
                    result = self.runner(step, context=ctx)
                run.step_results.append(result)
                if not result.get("ok", True):
                    raise RuntimeError(result.get("error") or f"step {step.index} failed")
            run.ok = True
        except Exception as exc:  # noqa: BLE001
            run.ok = False
            run.error = str(exc)
        run.finished_at = _utc_iso()
        routine.last_runs.append(run)
        self.store.save(routine)
        return run
