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
from .llm_planner import polish_plan_with_llm
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
        llm_polish: bool = False,
        llm_caller: Any | None = None,
    ) -> None:
        self.store = store
        self.runner_factory = runner_factory or (lambda d: LiveStepRunner(d, allow_net=False))
        self.max_retries = max_retries
        self.llm_polish = llm_polish
        self.llm_caller = llm_caller
        self.skill_ids: list[str] = []
        self.skills_work_root: Path | None = None
        self.skills_root_override: Path | None = None

    def bind_skills(
        self,
        skill_ids: list[str],
        *,
        work_root: Path | None = None,
        skills_root: Path | None = None,
    ) -> None:
        self.skill_ids = list(skill_ids)
        self.skills_work_root = Path(work_root) if work_root else Path("artifacts") / "skillhub"
        self.skills_root_override = Path(skills_root) if skills_root else None

    def _skill_context(self) -> str:
        if not self.skill_ids:
            return ""
        from ..skills import SkillCatalog, SkillRuntime

        if self.skills_root_override is not None:
            cat = SkillCatalog(skills_root=self.skills_root_override, include_builtin=False)
        else:
            cat = SkillCatalog()
        rt = SkillRuntime(
            cat,
            work_root=self.skills_work_root or Path("artifacts") / "skillhub",
        )
        for sid in self.skill_ids:
            try:
                rt.enable(sid)
            except KeyError:
                continue
        return rt.compose_system(self.skill_ids, max_chars=4000)

    def plan(self, goal: str, *, use_llm: bool | None = None) -> GoalPlan:
        plan = plan_goal(goal, skill_context=self._skill_context())
        if use_llm if use_llm is not None else self.llm_polish:
            plan = polish_plan_with_llm(plan, caller=self.llm_caller)
        return plan

    def run(
        self,
        goal: str,
        *,
        plan: GoalPlan | None = None,
        work_dir: Path | None = None,
        approvals: set[str] | None = None,
        mode: str = "live",
        use_llm: bool | None = None,
        on_event: Callable[[dict[str, Any]], None] | None = None,
    ) -> GoalRun:
        def emit(kind: str, **kwargs: Any) -> None:
            if on_event is None:
                return
            try:
                on_event({"kind": kind, **kwargs})
            except Exception:
                pass

        plan = plan or self.plan(goal, use_llm=use_llm)
        emit(
            "plan",
            steps=len(plan.steps),
            step_kinds=[s.kind for s in plan.steps],
            message=f"已规划 {len(plan.steps)} 步",
        )
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
                    emit("error", message=run.error, terminal=True)
                    break

                total = len(plan.steps)
                for step in plan.steps:
                    emit(
                        "step_start",
                        index=step.index,
                        total=total,
                        step_kind=step.kind,
                        instruction=step.instruction[:200],
                        message=f"步骤 {step.index + 1}/{total}：{step.kind}",
                    )
                    result = runner(
                        _to_draft_step(step),
                        context={"mode": mode, "goal_id": run_id, "routine_id": run_id},
                    )
                    step_results.append(result)
                    emit(
                        "step_end",
                        index=step.index,
                        total=total,
                        ok=bool(result.get("ok")),
                        message=(
                            f"步骤 {step.index + 1} 完成"
                            if result.get("ok")
                            else f"步骤 {step.index + 1} 失败"
                        ),
                    )
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
                    emit("accepted", message="验收通过", terminal=True)
                    break

                run.retries = attempt
                if attempt >= self.max_retries:
                    run.status = "rejected"
                    failed = [r.criterion_id for r in accept_results if not r.ok]
                    run.error = f"acceptance failed: {failed}"
                    emit("failed", message=run.error, terminal=True)
                    break

                attempt += 1
                run.retries = attempt
                emit("retry", attempt=attempt, message=f"重试第 {attempt} 次")
        except Exception as exc:  # noqa: BLE001
            run.status = "error"
            run.error = str(exc)
            emit("error", message=str(exc), terminal=True)

        run.finished_at = _utc_iso()
        self.store.save_run(run)
        if run.status == "accepted":
            emit("done", status=run.status, terminal=True, message="执行完成")
        elif run.status not in {"error", "rejected"}:
            emit("done", status=run.status, terminal=True)
        return run
