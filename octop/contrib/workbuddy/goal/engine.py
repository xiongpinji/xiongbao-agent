# SPDX-License-Identifier: MIT
"""GoalEngine — plan → execute (LiveStepRunner) → accept → optional retry."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from ..routine.live_runner import LiveStepRunner
from ..teach.models import DraftStep
from .acceptor import accept_all
from .models import GoalPlan, GoalRun, PlanStep
from .planner import plan_goal
from .store import GoalStore


def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _to_draft_step(step: PlanStep) -> DraftStep:
    return DraftStep(
        index=step.index,
        kind=step.kind,  # type: ignore[arg-type]
        instruction=step.instruction,
        requires_approval=step.requires_approval,
    )


class GoalEngine:
    """Craft-mode MVP: natural language goal with acceptance loop."""

    def __init__(
        self,
        store: GoalStore,
        *,
        runner_factory: Callable[[Path], Any] | None = None,
        max_retries: int = 1,
    ) -> None:
        self.store = store
        self.runner_factory = runner_factory or (lambda d: LiveStepRunner(d, allow_net=False))
        self.max_retries = max_retries

    def plan(self, goal: str) -> GoalPlan:
        return plan_goal(goal)

    def run(
        self,
        goal: str,
        *,
        plan: GoalPlan | None = None,
        work_dir: Path | None = None,
        approvals: set[str] | None = None,
        mode: str = "live",
    ) -> GoalRun:
        plan = plan or self.plan(goal)
        run_id = f"goal-{uuid.uuid4().hex[:10]}"
        work = Path(work_dir) if work_dir else self.store.root / "work" / run_id
        work.mkdir(parents=True, exist_ok=True)
        run = GoalRun(
            id=run_id,
            goal=goal,
            plan=plan,
            status="running",
            work_dir=str(work),
        )
        approvals = approvals or set()
        # Auto-approve planned steps that declare requires_approval when caller
        # passes --approve-all or explicit step ids.
        needed = {f"step:{s.index}" for s in plan.steps if s.requires_approval}
        if "all" in approvals:
            approvals = approvals | needed

        try:
            attempt = 0
            while True:
                runner = self.runner_factory(work)
                step_results: list[dict[str, Any]] = []
                blocked = needed - approvals
                if blocked:
                    run.status = "error"
                    run.error = f"missing approvals: {sorted(blocked)}"
                    break

                for step in plan.steps:
                    result = runner(
                        _to_draft_step(step),
                        context={"mode": mode, "goal_id": run_id, "routine_id": run_id},
                    )
                    step_results.append(result)
                    if not result.get("ok"):
                        break

                run.step_results = step_results
                ok, accept_results = accept_all(
                    plan.criteria,
                    work_dir=work,
                    step_results=step_results,
                )
                run.accept_results = accept_results
                if ok:
                    run.status = "accepted"
                    break

                run.retries = attempt
                if attempt >= self.max_retries:
                    run.status = "rejected"
                    failed = [r.criterion_id for r in accept_results if not r.ok]
                    run.error = f"acceptance failed: {failed}"
                    break

                # Retry: clear failed write artifacts then re-run (idempotent overwrite)
                attempt += 1
                run.retries = attempt
        except Exception as exc:  # noqa: BLE001
            run.status = "error"
            run.error = str(exc)

        run.finished_at = _utc_iso()
        self.store.save_run(run)
        return run
