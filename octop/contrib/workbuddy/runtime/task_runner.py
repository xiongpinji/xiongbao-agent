# SPDX-License-Identifier: MIT
"""Run a Task through GoalEngine (dry or live)."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..goal import GoalEngine, GoalStore
from ..task import TaskStore
from .kb_context import kb_prompt_prefix
from .policy_gate import check_run_allowed
from .profile_env import apply_profile_env


@dataclass
class TaskRunResult:
    ok: bool
    task_id: str
    mode: str
    dry_run: bool
    goal_run_id: str = ""
    status: str = ""
    detail: dict[str, Any] = field(default_factory=dict)
    error: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "task_id": self.task_id,
            "mode": self.mode,
            "dry_run": self.dry_run,
            "goal_run_id": self.goal_run_id,
            "status": self.status,
            "detail": dict(self.detail),
            "error": self.error,
        }


def _goal_text(store: TaskStore, task_id: str, *, kb_root: Path | None) -> str:
    rec = store.get(task_id)
    parts: list[str] = []
    if kb_root is not None:
        prefix = kb_prompt_prefix(kb_root, rec.title or task_id, limit=3)
        if prefix:
            parts.append(prefix)
    for msg in rec.messages:
        if msg.role == "user" and msg.content.strip():
            parts.append(msg.content.strip())
    if not parts:
        parts.append(rec.title or task_id)
    return "\n\n".join(parts)


def run_task(
    task_id: str,
    *,
    tasks_root: Path | str = "artifacts/tasks",
    goals_root: Path | str = "artifacts/goal_craft",
    policy_path: Path | str | None = None,
    profiles_path: Path | str | None = None,
    kb_root: Path | str | None = "artifacts/knowledge",
    dry_run: bool = True,
    approve_all: bool = True,
) -> TaskRunResult:
    """Execute task.prompt via GoalEngine; dry_run plans only and marks waiting."""
    store = TaskStore(tasks_root)
    try:
        rec = store.get(task_id)
    except FileNotFoundError as exc:
        return TaskRunResult(False, task_id, "", dry_run, error=str(exc))

    gate = check_run_allowed(
        mode=rec.mode,
        policy_path=policy_path,
        needs_write=not dry_run,
        needs_shell=False,
        needs_outbound=False,
    )
    if not gate.allowed and not dry_run:
        return TaskRunResult(
            False,
            task_id,
            rec.mode,
            dry_run,
            status=rec.status,
            detail={"policy": gate.to_dict()},
            error=gate.reason,
        )

    apply_profile_env(path=profiles_path)

    goal = _goal_text(
        store,
        task_id,
        kb_root=Path(kb_root) if kb_root else None,
    )

    if dry_run:
        from ..goal.planner import plan_goal

        plan = plan_goal(goal)
        store.set_status(task_id, "waiting")
        store.append_message(
            task_id,
            "system",
            f"[dry-run] planned {len(plan.steps)} steps — not executed",
        )
        store.add_result(
            task_id,
            {
                "kind": "dry_run_plan",
                "steps": [s.to_dict() for s in plan.steps],
                "criteria": [c.to_dict() for c in plan.criteria],
            },
        )
        return TaskRunResult(
            True,
            task_id,
            rec.mode,
            True,
            status="waiting",
            detail={
                "plan_steps": len(plan.steps),
                "policy": gate.to_dict(),
                "goal_preview": goal[:400],
            },
        )

    # live path
    store.set_status(task_id, "running")
    gstore = GoalStore(goals_root)
    engine = GoalEngine(gstore)
    approvals = {"all"} if approve_all else set()
    run = engine.run(goal, mode="live", approvals=approvals)
    store.link_goal(task_id, run.id)
    store.set_status(task_id, "completed" if run.status == "accepted" else "failed")
    store.add_result(
        task_id,
        {
            "kind": "goal_run",
            "run_id": run.id,
            "status": run.status,
            "error": run.error or "",
        },
    )
    store.append_message(
        task_id,
        "assistant",
        f"goal run {run.id} → {run.status}",
    )
    return TaskRunResult(
        ok=run.status == "accepted",
        task_id=task_id,
        mode=rec.mode,
        dry_run=False,
        goal_run_id=run.id,
        status=run.status,
        detail={"error": run.error or "", "policy": gate.to_dict()},
        error=run.error or "",
    )
