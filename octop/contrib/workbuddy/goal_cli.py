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


def cmd_demo(args: argparse.Namespace) -> int:
    root = Path(args.root)
    store = GoalStore(root)
    engine = GoalEngine(
        store,
        runner_factory=lambda d: LiveStepRunner(d, allow_net=False, allow_outbound=False),
        llm_polish=bool(args.llm),
    )
    _bind_engine_skills(engine, args)
    goal = args.goal or "把今日 PR 摘要写入 pr-summary.md 并通知飞书群"
    run = engine.run(goal, approvals={"all"}, mode="live")
    print(json.dumps(run.to_dict(), ensure_ascii=False, indent=2))
    print(f"GOAL DEMO {'OK' if run.ok else 'FAIL'} id={run.id} status={run.status}")
    return 0 if run.ok else 1


def cmd_plan(args: argparse.Namespace) -> int:
    engine = GoalEngine(GoalStore(Path(args.root)), llm_polish=bool(args.llm))
    _bind_engine_skills(engine, args)
    plan = engine.plan(args.goal, use_llm=bool(args.llm))
    print(json.dumps(plan.to_dict(), ensure_ascii=False, indent=2))
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    root = Path(args.root)
    store = GoalStore(root)
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
        args.goal,
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
