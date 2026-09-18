# SPDX-License-Identifier: MIT
"""CLI for Teach → SkillDraft → Routine (V2 MVP).

Examples::

    python -S -m octop.contrib.workbuddy.teach_cli demo
    python -S -m octop.contrib.workbuddy.teach_cli demo --llm
    python -S -m octop.contrib.workbuddy.teach_cli polish --name notion-pr-to-feishu --llm
    python -S -m octop.contrib.workbuddy.teach_cli cdp-record --url https://example.com --seconds 20
    python -S -m octop.contrib.workbuddy.teach_cli run --routine-id <id> --mode live --live-runner --cdp-replay
    python -S -m octop.contrib.workbuddy.teach_cli connectors
    python -S -m octop.contrib.workbuddy.teach_cli due
    python -S -m octop.contrib.workbuddy.teach_cli tick --mode dry
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from .routine import LiveStepRunner, RoutineEngine, RoutineScheduler, RoutineStore
from .teach import (
    CdpReplaySession,
    CdpTeachSession,
    TeachRecorder,
    TeachStore,
    cdp_available,
    draft_skill_from_recording,
    polish_draft_with_llm,
)
from .teach.cdp_client import CdpError
from .team.llm import OpenAICompatCaller
from .connectors import FeishuConnector, NotionConnector, probe_status


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
    if args.llm:
        draft = polish_draft_with_llm(
            draft,
            caller=OpenAICompatCaller(max_tokens=1024, temperature=0.2),
            fallback_on_error=True,
        )
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
            "source": draft.source,
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


def cmd_polish(args: argparse.Namespace) -> int:
    store = TeachStore(Path(args.root) / "teach")
    draft = store.load_draft(args.name)
    if not args.llm:
        print("polish requires --llm", file=sys.stderr)
        return 2
    polished = polish_draft_with_llm(
        draft,
        caller=OpenAICompatCaller(max_tokens=1024, temperature=0.2),
        fallback_on_error=bool(args.fallback),
    )
    store.save_draft(polished)
    print(
        json.dumps(
            {
                "name": polished.name,
                "source": polished.source,
                "status": polished.status,
                "trigger": polished.trigger,
                "steps": [s.to_dict() for s in polished.steps],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if polished.source == "rules+llm" else (0 if args.fallback else 1)


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


def cmd_cdp_record(args: argparse.Namespace) -> int:
    """Attach to Chrome CDP and record page actions into a TeachRecording."""
    root = Path(args.root)
    teach_store = TeachStore(root / "teach")
    host = args.host
    port = int(args.port)
    if not cdp_available(host, port):
        print(
            f"CDP not reachable at {host}:{port}. "
            "Start Chrome with --remote-debugging-port=9222",
            file=sys.stderr,
        )
        return 2
    rec = TeachRecorder(
        bot_id=args.bot_id,
        intent=args.intent or f"CDP 录制 {args.url or 'current page'}",
        store_dir=teach_store.recordings_dir,
    )
    try:
        session = CdpTeachSession.attach(
            rec,
            host=host,
            port=port,
            navigate_url=args.url,
            page_url_substr=args.page_match,
        )
    except CdpError as exc:
        print(f"CDP attach failed: {exc}", file=sys.stderr)
        return 2
    try:
        n = session.record_for(float(args.seconds))
    finally:
        session.close()
    recording = rec.close()
    teach_store.save_recording(recording)
    payload = {
        "recording_id": recording.id,
        "events_drained": n,
        "steps": len(recording.steps),
        "kinds": [s.kind for s in recording.steps],
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    print(f"CDP RECORD OK id={recording.id}")
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    teach_store = TeachStore(Path(args.root) / "teach")
    routine_store = RoutineStore(Path(args.root) / "routines")
    routine = routine_store.load(args.routine_id)
    draft = teach_store.load_draft(routine.skill_name)
    runner = None
    cdp = None
    if args.live_runner or args.cdp_replay or args.outbound:
        work = (
            Path(args.live_work_dir)
            if args.live_work_dir
            else Path(args.root) / "live_work" / args.routine_id
        )
        if args.cdp_replay:
            try:
                cdp = CdpReplaySession.attach(
                    host=args.cdp_host,
                    port=int(args.cdp_port),
                    page_url_substr=args.page_match,
                )
            except CdpError as exc:
                print(f"CDP replay attach failed: {exc}", file=sys.stderr)
                return 2
        runner = LiveStepRunner(
            work,
            allow_net=not bool(args.no_net),
            cdp_replay=cdp,
            notion=NotionConnector(),
            feishu=FeishuConnector(),
            allow_outbound=bool(args.outbound),
        )
    engine = RoutineEngine(routine_store, runner=runner)
    approvals = set(args.approve or [])
    try:
        run = engine.run(
            routine,
            draft,
            mode=args.mode,  # type: ignore[arg-type]
            approvals=approvals,
            confirm_test=bool(args.confirm_test),
        )
    finally:
        if cdp is not None:
            cdp.close()
    print(json.dumps(run.to_dict(), ensure_ascii=False, indent=2))
    return 0 if run.ok else 1


def cmd_connectors(args: argparse.Namespace) -> int:
    status = probe_status()
    print(json.dumps(status, ensure_ascii=False, indent=2))
    if args.probe_notion:
        nc = NotionConnector()
        if not nc.configured():
            print("FAIL: WB_NOTION_TOKEN not set", file=sys.stderr)
            return 2
        res = nc.read_target(args.probe_notion)
        print(json.dumps(res.to_dict(), ensure_ascii=False, indent=2))
        return 0 if res.ok else 1
    if args.probe_feishu:
        fc = FeishuConnector()
        os.environ["WB_ALLOW_OUTBOUND"] = "1"
        res = fc.send_text(args.probe_feishu, require_outbound_flag=True)
        print(json.dumps(res.to_dict(), ensure_ascii=False, indent=2))
        return 0 if res.ok else 1
    return 0


def cmd_due(args: argparse.Namespace) -> int:
    root = Path(args.root)
    sched = RoutineScheduler(
        RoutineStore(root / "routines"),
        TeachStore(root / "teach"),
    )
    print(json.dumps(sched.preview(), ensure_ascii=False, indent=2))
    return 0


def cmd_tick(args: argparse.Namespace) -> int:
    root = Path(args.root)
    routine_store = RoutineStore(root / "routines")
    engine = RoutineEngine(routine_store)
    sched = RoutineScheduler(routine_store, TeachStore(root / "teach"), engine)
    results = sched.tick(
        mode=args.mode,  # type: ignore[arg-type]
        confirm_test=bool(args.confirm_test),
        approvals=set(args.approve or []),
    )
    payload = {
        "fired": sum(1 for r in results if r.fired),
        "results": [r.to_dict() for r in results],
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    if results and any(r.error or (r.run and not r.run.ok) for r in results):
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Teach / Routine V2 CLI")
    parser.add_argument("--root", default=str(_default_root()))
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_demo = sub.add_parser("demo", help="Record → draft → approve → routine dry-run")
    p_demo.add_argument("--bot-id", default="demo-bot")
    p_demo.add_argument("--cron", default="0 9 * * *")
    p_demo.add_argument("--timezone", default="Asia/Shanghai")
    p_demo.add_argument("--out", default="artifacts/teach_routine/demo_report.json")
    p_demo.add_argument(
        "--llm",
        action="store_true",
        help="Polish SkillDraft with local OpenAI-compatible LLM before approve",
    )
    p_demo.set_defaults(func=cmd_demo)

    p_list = sub.add_parser("list")
    p_list.set_defaults(func=cmd_list)

    p_ap = sub.add_parser("approve")
    p_ap.add_argument("--name", required=True)
    p_ap.set_defaults(func=cmd_approve)

    p_pol = sub.add_parser("polish", help="LLM-polish an existing draft (resets to draft)")
    p_pol.add_argument("--name", required=True)
    p_pol.add_argument("--llm", action="store_true", required=True)
    p_pol.add_argument(
        "--fallback",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="On LLM failure keep rules draft (default: true)",
    )
    p_pol.set_defaults(func=cmd_polish)

    p_cr = sub.add_parser("create-routine")
    p_cr.add_argument("--skill", required=True)
    p_cr.add_argument("--bot-id", default="default")
    p_cr.add_argument("--cron", default="0 9 * * *")
    p_cr.add_argument("--timezone", default="Asia/Shanghai")
    p_cr.set_defaults(func=cmd_create_routine)

    p_cdp = sub.add_parser(
        "cdp-record",
        help="Attach Chrome CDP (--remote-debugging-port=9222) and record clicks/types/nav",
    )
    p_cdp.add_argument("--url", default=None, help="Optional Page.navigate URL before polling")
    p_cdp.add_argument("--seconds", type=float, default=15.0, help="Poll duration")
    p_cdp.add_argument("--host", default="127.0.0.1")
    p_cdp.add_argument("--port", type=int, default=9222)
    p_cdp.add_argument("--page-match", default=None, help="Prefer page whose URL contains this")
    p_cdp.add_argument("--bot-id", default="cdp-bot")
    p_cdp.add_argument("--intent", default=None)
    p_cdp.set_defaults(func=cmd_cdp_record)

    p_run = sub.add_parser("run")
    p_run.add_argument("--routine-id", required=True)
    p_run.add_argument("--mode", choices=["dry", "test", "live"], default="dry")
    p_run.add_argument("--approve", action="append", default=[])
    p_run.add_argument("--confirm-test", action="store_true")
    p_run.add_argument(
        "--live-runner",
        action="store_true",
        help="Use LiveStepRunner (sandbox files + outbox) for test/live modes",
    )
    p_run.add_argument(
        "--live-work-dir",
        default=None,
        help="Sandbox root for LiveStepRunner (default: <root>/live_work/<routine-id>)",
    )
    p_run.add_argument(
        "--no-net",
        action="store_true",
        help="With --live-runner, skip HTTP GET for navigate/read",
    )
    p_run.add_argument(
        "--cdp-replay",
        action="store_true",
        help="Attach Chrome CDP and replay click/type/navigate steps",
    )
    p_run.add_argument("--cdp-host", default="127.0.0.1")
    p_run.add_argument("--cdp-port", type=int, default=9222)
    p_run.add_argument("--page-match", default=None, help="Prefer CDP page URL substring")
    p_run.add_argument(
        "--outbound",
        action="store_true",
        help="Allow Feishu webhook send (needs WB_FEISHU_WEBHOOK)",
    )
    p_run.set_defaults(func=cmd_run)

    p_conn = sub.add_parser("connectors", help="Probe Notion/Feishu connector config")
    p_conn.add_argument(
        "--probe-notion",
        default=None,
        help="Read a Notion page id or URL (needs WB_NOTION_TOKEN)",
    )
    p_conn.add_argument(
        "--probe-feishu",
        default=None,
        help="Send a test text via WB_FEISHU_WEBHOOK",
    )
    p_conn.set_defaults(func=cmd_connectors)

    p_due = sub.add_parser("due", help="Preview schedule / due status for all routines")
    p_due.set_defaults(func=cmd_due)

    p_tick = sub.add_parser("tick", help="Fire all due routines for the current minute")
    p_tick.add_argument("--mode", choices=["dry", "test", "live"], default="dry")
    p_tick.add_argument("--approve", action="append", default=[])
    p_tick.add_argument("--confirm-test", action="store_true")
    p_tick.set_defaults(func=cmd_tick)

    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
