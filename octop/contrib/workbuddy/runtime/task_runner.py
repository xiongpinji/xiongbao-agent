# SPDX-License-Identifier: MIT
"""Run a Task through GoalEngine (dry or live)."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..goal import GoalEngine, GoalStore
from ..project import ProjectSpace
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


def _goal_text(
    store: TaskStore,
    task_id: str,
    *,
    kb_root: Path | None,
    project_memory: str = "",
) -> str:
    rec = store.get(task_id)
    parts: list[str] = []
    if project_memory.strip():
        parts.append("# 项目记忆\n\n" + project_memory.strip())
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


def _bind_project_skills(
    engine: GoalEngine,
    *,
    project_id: str,
    projects_root: Path,
    runtime_work: Path,
) -> list[str]:
    """Bind deposited project skills into GoalEngine; return skill ids."""
    if not project_id.strip():
        return []
    space = ProjectSpace(projects_root)
    try:
        space.load(project_id)
    except FileNotFoundError:
        return []
    skills_root = space.skills_root(project_id)
    # Prefer directories that contain SKILL.md (catalog scan units)
    ids = [
        p.name
        for p in sorted(skills_root.iterdir())
        if p.is_dir() and (p / "SKILL.md").is_file()
    ]
    if not ids:
        return []
    runtime_work.mkdir(parents=True, exist_ok=True)
    engine.bind_skills(ids, work_root=runtime_work, skills_root=skills_root)
    return ids


def run_task(
    task_id: str,
    *,
    tasks_root: Path | str = "artifacts/tasks",
    goals_root: Path | str = "artifacts/goal_craft",
    projects_root: Path | str | None = "artifacts/projects",
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

    proj_root = Path(projects_root) if projects_root else None
    project_memory = ""
    if proj_root is not None and rec.project_id:
        try:
            project_memory = ProjectSpace(proj_root).memory_text(rec.project_id)
        except Exception:  # noqa: BLE001
            project_memory = ""

    goal = _goal_text(
        store,
        task_id,
        kb_root=Path(kb_root) if kb_root else None,
        project_memory=project_memory,
    )

    task_dir = store._dir(task_id)
    bound_skills: list[str] = []

    if dry_run:
        from ..goal.planner import plan_goal

        # Dry-run still surfaces project skill context in the plan artifact body
        engine = GoalEngine(GoalStore(Path(goals_root)))
        if proj_root is not None and rec.project_id:
            bound_skills = _bind_project_skills(
                engine,
                project_id=rec.project_id,
                projects_root=proj_root,
                runtime_work=task_dir / "skill_runtime",
            )
        plan = engine.plan(goal) if bound_skills else plan_goal(goal)
        n_steps = len(plan.steps)
        skill_note = f"；已绑定项目技能 {len(bound_skills)} 个" if bound_skills else ""
        store.set_status(task_id, "waiting")
        store.append_message(
            task_id,
            "system",
            f"已完成演练：规划了 {n_steps} 步，未实际执行{skill_note}。取消「仅演练」后可正式运行。",
        )
        store.add_result(
            task_id,
            {
                "kind": "dry_run_plan",
                "steps": [s.to_dict() for s in plan.steps],
                "criteria": [c.to_dict() for c in plan.criteria],
                "project_id": rec.project_id,
                "bound_skills": bound_skills,
            },
        )
        return TaskRunResult(
            True,
            task_id,
            rec.mode,
            True,
            status="waiting",
            detail={
                "plan_steps": n_steps,
                "policy": gate.to_dict(),
                "goal_preview": goal[:400],
                "user_message": f"已完成演练（{n_steps} 步）",
                "project_id": rec.project_id,
                "bound_skills": bound_skills,
            },
        )

    # live path — write into the task workspace so the Results panel can see files
    store.set_status(task_id, "running")
    start_msg = "已开始执行，请稍候…"
    if rec.project_id:
        start_msg = f"已开始执行（项目空间 `{rec.project_id}`），请稍候…"
    store.append_message(task_id, "assistant", start_msg)
    work = task_dir / "workspace"
    work.mkdir(parents=True, exist_ok=True)
    gstore = GoalStore(goals_root)
    engine = GoalEngine(gstore)
    if proj_root is not None and rec.project_id:
        bound_skills = _bind_project_skills(
            engine,
            project_id=rec.project_id,
            projects_root=proj_root,
            runtime_work=task_dir / "skill_runtime",
        )
        if bound_skills:
            store.append_message(
                task_id,
                "system",
                "已加载项目技能：" + "、".join(bound_skills[:12]),
            )
    approvals = {"all"} if approve_all else set()
    run = engine.run(goal, mode="live", approvals=approvals, work_dir=work)
    store.link_goal(task_id, run.id)
    final_status = "completed" if run.status == "accepted" else "failed"
    store.set_status(task_id, final_status)

    produced: list[str] = []
    if work.is_dir():
        for p in sorted(work.rglob("*")):
            if not p.is_file():
                continue
            if p.name in {"live_steps.jsonl"}:
                continue
            produced.append(p.relative_to(task_dir).as_posix())

    store.add_result(
        task_id,
        {
            "kind": "goal_run",
            "run_id": run.id,
            "status": run.status,
            "error": run.error or "",
            "work_dir": str(work),
            "artifacts": produced[:40],
            "project_id": rec.project_id,
            "bound_skills": bound_skills,
        },
    )
    if run.status == "accepted":
        if produced:
            preview = "、".join(produced[:5])
            more = f" 等 {len(produced)} 个文件" if len(produced) > 5 else ""
            user_msg = f"执行完成，已生成：{preview}{more}。可在右侧查看产物与预览。"
        else:
            user_msg = "执行完成，但任务目录下暂无新文件。可在右侧「变更」查看执行记录。"
        if bound_skills:
            user_msg += f"（已用项目技能：{'、'.join(bound_skills[:5])}）"
    else:
        err = (run.error or run.status or "未知错误").strip()
        user_msg = f"执行未成功：{err}"
    store.append_message(task_id, "assistant", user_msg)
    return TaskRunResult(
        ok=run.status == "accepted",
        task_id=task_id,
        mode=rec.mode,
        dry_run=False,
        goal_run_id=run.id,
        status=final_status,
        detail={
            "error": run.error or "",
            "policy": gate.to_dict(),
            "goal_status": run.status,
            "user_message": user_msg,
            "artifacts": produced[:40],
            "project_id": rec.project_id,
            "bound_skills": bound_skills,
        },
        error=run.error or "",
    )
