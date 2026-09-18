# SPDX-License-Identifier: MIT
"""CLI for Goal / Craft (plan → execute → accept).

Examples::

    python -S -m octop.contrib.workbuddy.goal_cli demo
    python -S -m octop.contrib.workbuddy.goal_cli plan --goal "写入 weekly.md 并通知飞书"
    python -S -m octop.contrib.workbuddy.goal_cli run --goal "写入 report.md 并通知飞书" --approve-all
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .goal import GoalEngine, GoalStore
from .routine import LiveStepRunner


def _default_root() -> Path:
    return Path("artifacts") / "goal_craft"


def _bind_engine_skills(engine: GoalEngine, args: argparse.Namespace) -> None:
    skills = list(getattr(args, "skill", None) or [])
    if skills:
        engine.bind_skills(
            skills,
            work_root=Path(getattr(args, "skills_work_root", None) or "artifacts/skillhub"),
        )


def _resolve_work_mode(args: argparse.Namespace) -> str:
    from .modes import normalize_mode

    return normalize_mode(getattr(args, "work_mode", None) or "craft")


def _inject_workspace_goal(goal: str, args: argparse.Namespace) -> str:
    """Prefix goal with mode gate + optional workspace memory."""
    from .memory import load_workspace_memory
    from .modes import assemble_system_prompt, mode_allows_writes

    mode = _resolve_work_mode(args)
    soul = user = durable = daily = ""
    ws = getattr(args, "workspace", None)
    if ws:
        mem = load_workspace_memory(ws)
        soul, user, durable, daily = mem.soul, mem.user, mem.durable, mem.daily
    assembled = assemble_system_prompt(
        mode=mode,
        soul=soul,
        user_profile=user,
        working_memory=daily,
        durable_memory=durable,
    )
    parts = [
        f"[Work mode: {mode} | writes={'yes' if mode_allows_writes(mode) else 'no'}]",
        assembled.sections[-1],
    ]
    if soul or user or durable or daily:
        bits = []
        if soul:
            bits.append("SOUL: " + soul[:800])
        if user:
            bits.append("USER: " + user[:800])
        if durable:
            bits.append("MEMORY: " + durable[:800])
        if daily:
            bits.append("DAILY: " + daily[:800])
        parts.append("[Workspace]\n" + "\n".join(bits))
    parts.append("[Goal]\n" + goal)
    return "\n\n".join(parts)


def _add_skill_flags(sp: argparse.ArgumentParser) -> None:
    sp.add_argument(
        "--skill",
        action="append",
        default=[],
        help="Bind SkillHub skill id(s) into write artifact (repeatable)",
    )
    sp.add_argument(
        "--skills-work-root",
        default="artifacts/skillhub",
        help="SkillRuntime work root",
    )
    sp.add_argument(
        "--work-mode",
        default="craft",
        choices=["ask", "plan", "craft"],
        help="Ask/Plan/Craft gate (ask/plan refuse mutating run)",
    )
    sp.add_argument(
        "--workspace",
        default=None,
        help="Workspace with SOUL.md / USER.md / MEMORY.md",
    )


def cmd_demo(args: argparse.Namespace) -> int:
    from .modes import mode_allows_writes

    root = Path(args.root)
    store = GoalStore(root)
    engine = GoalEngine(
        store,
        runner_factory=lambda d: LiveStepRunner(d, allow_net=False, allow_outbound=False),
        llm_polish=bool(args.llm),
    )
    _bind_engine_skills(engine, args)
    goal = args.goal or "把今日 PR 摘要写入 pr-summary.md 并通知飞书群"
    goal = _inject_workspace_goal(goal, args)
    mode = _resolve_work_mode(args)
    if not mode_allows_writes(mode):
        plan = engine.plan(goal, use_llm=bool(args.llm))
        print(json.dumps({"mode": mode, "refused_run": True, "plan": plan.to_dict()}, ensure_ascii=False, indent=2))
        print(f"GOAL DEMO PLAN-ONLY mode={mode}")
        return 0
    run = engine.run(goal, approvals={"all"}, mode="live")
    print(json.dumps(run.to_dict(), ensure_ascii=False, indent=2))
    print(f"GOAL DEMO {'OK' if run.ok else 'FAIL'} id={run.id} status={run.status}")
    return 0 if run.ok else 1


def cmd_plan(args: argparse.Namespace) -> int:
    engine = GoalEngine(GoalStore(Path(args.root)), llm_polish=bool(args.llm))
    _bind_engine_skills(engine, args)
    goal = _inject_workspace_goal(args.goal, args)
    plan = engine.plan(goal, use_llm=bool(args.llm))
    print(json.dumps({"mode": _resolve_work_mode(args), "plan": plan.to_dict()}, ensure_ascii=False, indent=2))
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    from .modes import mode_allows_writes

    root = Path(args.root)
    store = GoalStore(root)
    work_mode = _resolve_work_mode(args)
    goal = _inject_workspace_goal(args.goal, args)
    if not mode_allows_writes(work_mode):
        engine = GoalEngine(store, llm_polish=bool(args.llm))
        _bind_engine_skills(engine, args)
        plan = engine.plan(goal, use_llm=bool(args.llm))
        print(
            json.dumps(
                {
                    "ok": False,
                    "mode": work_mode,
                    "error": f"work-mode={work_mode} refuses mutating run; use --work-mode craft",
                    "plan": plan.to_dict(),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 2
    approvals: set[str] = set(args.approve or [])
    if args.approve_all:
        approvals.add("all")
    engine = GoalEngine(
        store,
        runner_factory=lambda d: LiveStepRunner(
            d,
            allow_net=not bool(args.no_net),
            allow_outbound=bool(args.outbound),
        ),
        max_retries=int(args.retries),
        llm_polish=bool(args.llm),
    )
    _bind_engine_skills(engine, args)
    run = engine.run(
        goal,
        work_dir=Path(args.work_dir) if args.work_dir else None,
        approvals=approvals,
        mode=args.mode,
    )
    print(json.dumps(run.to_dict(), ensure_ascii=False, indent=2))
    return 0 if run.ok else 1


def cmd_list(args: argparse.Namespace) -> int:
    store = GoalStore(Path(args.root))
    print(json.dumps({"runs": store.list_runs()}, ensure_ascii=False, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="goal_cli", description="Goal/Craft MVP")
    p.add_argument("--root", default=str(_default_root()), help="Store root (also allowed on subcommands)")
    sub = p.add_subparsers(dest="cmd", required=True)

    def _add_root(sp: argparse.ArgumentParser) -> None:
        sp.add_argument("--root", default=str(_default_root()))

    p_demo = sub.add_parser("demo", help="End-to-end demo with default goal")
    _add_root(p_demo)
    _add_skill_flags(p_demo)
    p_demo.add_argument("--goal", default=None)
    p_demo.add_argument("--llm", action="store_true", help="Polish plan with local LLM")
    p_demo.set_defaults(func=cmd_demo)

    p_plan = sub.add_parser("plan", help="Show planned steps + criteria only")
    _add_root(p_plan)
    _add_skill_flags(p_plan)
    p_plan.add_argument("--goal", required=True)
    p_plan.add_argument("--llm", action="store_true", help="Polish plan with local LLM")
    p_plan.set_defaults(func=cmd_plan)

    p_run = sub.add_parser("run", help="Plan + execute + accept")
    _add_root(p_run)
    _add_skill_flags(p_run)
    p_run.add_argument("--goal", required=True)
    p_run.add_argument("--work-dir", default=None)
    p_run.add_argument("--mode", default="live", choices=["live", "test", "dry"])
    p_run.add_argument("--approve", action="append", default=[])
    p_run.add_argument("--approve-all", action="store_true")
    p_run.add_argument("--retries", type=int, default=1)
    p_run.add_argument("--no-net", action="store_true")
    p_run.add_argument("--outbound", action="store_true")
    p_run.add_argument("--llm", action="store_true", help="Polish plan with local LLM")
    p_run.set_defaults(func=cmd_run)

    p_list = sub.add_parser("list", help="List saved goal runs")
    _add_root(p_list)
    p_list.set_defaults(func=cmd_list)
    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
