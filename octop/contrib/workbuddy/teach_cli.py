# SPDX-License-Identifier: MIT
"""CLI for Teach → SkillDraft → Routine (V2 MVP).

Examples::

    python -S -m octop.contrib.workbuddy.teach_cli demo
    python -S -m octop.contrib.workbuddy.teach_cli list
    python -S -m octop.contrib.workbuddy.teach_cli run --routine-id <id> --mode dry
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .routine import RoutineEngine, RoutineStore
from .teach import TeachRecorder, TeachStore, draft_skill_from_recording


def _default_root() -> Path:
    return Path("artifacts") / "teach_routine"


def cmd_demo(args: argparse.Namespace) -> int:
    """End-to-end demo: Notion PR scrape → Feishu notify (recorded path)."""
    root = Path(args.root)
    teach_store = TeachStore(root / "teach")
    routine_store = RoutineStore(root / "routines")

    rec = TeachRecorder(
        bot_id=args.bot_id,
        intent="打开 Notion 抓取今日 PR 列表并写入飞书群",
        store_dir=teach_store.recordings_dir,
    )
    rec.navigate("https://notion.so/workspace/prs", "打开 Notion PR 看板")
    rec.read_data("notion:today-pr-list", "抓取今日 PR 列表")
    rec.decision("PR 列表是否非空？空则中止并通知")
    rec.append(
        "message",
        "将 PR 摘要发送到飞书群",
        target="feishu:group/eng",
        tool_name="send",
        meta={"channel": "feishu"},
    )
    recording = rec.close()
    teach_store.save_recording(recording)

    draft = draft_skill_from_recording(recording, name="notion-pr-to-feishu")
    teach_store.save_draft(draft)

    # Human review gate
    draft = teach_store.approve_draft(draft.name)

    engine = RoutineEngine(routine_store)
    routine = engine.create_from_draft(
        draft,
        bot_id=args.bot_id,
        cron=args.cron,
        timezone=args.timezone,
    )
    run = engine.run(routine, draft, mode="dry")

    payload = {
        "recording_id": recording.id,
        "skill": draft.to_dict(),
        "routine": routine.to_dict(),
        "dry_run": run.to_dict(),
        "checks": {
            "steps": len(draft.steps),
            "decisions": sum(1 for s in draft.steps if s.is_decision),
            "approvals": len(draft.approvals),
            "dry_ok": run.ok,
        },
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload["checks"], ensure_ascii=False, indent=2))
    print(f"RECOMMENDED skill={draft.name} routine={routine.id}")
    print(f"wrote {out}")
    if not run.ok or len(draft.steps) < 3 or len(draft.approvals) < 1:
        print("FAIL: demo acceptance gate", file=sys.stderr)
        return 2
    print("TEACH/ROUTINE DEMO OK")
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    root = Path(args.root)
    teach_store = TeachStore(root / "teach")
    routine_store = RoutineStore(root / "routines")
    print(
        json.dumps(
            {
                "recordings": teach_store.list_recordings(),
                "drafts": teach_store.list_drafts(),
                "routines": routine_store.list_ids(),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def cmd_approve(args: argparse.Namespace) -> int:
    store = TeachStore(Path(args.root) / "teach")
    draft = store.approve_draft(args.name)
    print(json.dumps(draft.to_dict(), ensure_ascii=False, indent=2))
    return 0


def cmd_create_routine(args: argparse.Namespace) -> int:
    teach_store = TeachStore(Path(args.root) / "teach")
    routine_store = RoutineStore(Path(args.root) / "routines")
    draft = teach_store.load_draft(args.skill)
    engine = RoutineEngine(routine_store)
    routine = engine.create_from_draft(
        draft,
        bot_id=args.bot_id,
        cron=args.cron,
        timezone=args.timezone,
    )
    print(json.dumps(routine.to_dict(), ensure_ascii=False, indent=2))
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    teach_store = TeachStore(Path(args.root) / "teach")
    routine_store = RoutineStore(Path(args.root) / "routines")
    routine = routine_store.load(args.routine_id)
    draft = teach_store.load_draft(routine.skill_name)
    engine = RoutineEngine(routine_store)
    approvals = set(args.approve or [])
    run = engine.run(
        routine,
        draft,
        mode=args.mode,  # type: ignore[arg-type]
        approvals=approvals,
        confirm_test=bool(args.confirm_test),
    )
    print(json.dumps(run.to_dict(), ensure_ascii=False, indent=2))
    return 0 if run.ok else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Teach / Routine V2 CLI")
    parser.add_argument("--root", default=str(_default_root()))
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_demo = sub.add_parser("demo", help="Record → draft → approve → routine dry-run")
    p_demo.add_argument("--bot-id", default="demo-bot")
    p_demo.add_argument("--cron", default="0 9 * * *")
    p_demo.add_argument("--timezone", default="Asia/Shanghai")
    p_demo.add_argument("--out", default="artifacts/teach_routine/demo_report.json")
    p_demo.set_defaults(func=cmd_demo)

    p_list = sub.add_parser("list")
    p_list.set_defaults(func=cmd_list)

    p_ap = sub.add_parser("approve")
    p_ap.add_argument("--name", required=True)
    p_ap.set_defaults(func=cmd_approve)

    p_cr = sub.add_parser("create-routine")
    p_cr.add_argument("--skill", required=True)
    p_cr.add_argument("--bot-id", default="default")
    p_cr.add_argument("--cron", default="0 9 * * *")
    p_cr.add_argument("--timezone", default="Asia/Shanghai")
    p_cr.set_defaults(func=cmd_create_routine)

    p_run = sub.add_parser("run")
    p_run.add_argument("--routine-id", required=True)
    p_run.add_argument("--mode", choices=["dry", "test", "live"], default="dry")
    p_run.add_argument("--approve", action="append", default=[])
    p_run.add_argument("--confirm-test", action="store_true")
    p_run.set_defaults(func=cmd_run)

    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
