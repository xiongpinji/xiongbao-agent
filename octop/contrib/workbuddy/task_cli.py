# SPDX-License-Identifier: MIT
"""CLI for WorkBuddy task lifecycle."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .task import TaskStore


def _store(args: argparse.Namespace) -> TaskStore:
    root = Path(args.root) if getattr(args, "root", None) else Path("artifacts/tasks")
    return TaskStore(root)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="task_cli", description="WorkBuddy task lifecycle")
    p.add_argument("--root", default="artifacts/tasks")
    sub = p.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("create")
    c.add_argument("--title", required=True)
    c.add_argument("--id", dest="task_id", default=None)
    c.add_argument("--mode", default="craft", choices=["ask", "plan", "craft"])
    c.add_argument("--project", default="")
    c.add_argument("--prompt", default="")

    g = sub.add_parser("get")
    g.add_argument("task_id")

    l = sub.add_parser("list")
    l.add_argument("--status", default=None)

    s = sub.add_parser("status")
    s.add_argument("task_id")
    s.add_argument("--set", dest="new_status", required=True)

    a = sub.add_parser("append")
    a.add_argument("task_id")
    a.add_argument("--role", default="user", choices=["user", "assistant", "system"])
    a.add_argument("--content", required=True)

    r = sub.add_parser("result")
    r.add_argument("task_id")
    r.add_argument("--json", dest="result_json", required=True)

    done = sub.add_parser("complete")
    done.add_argument("task_id")
    done.add_argument("--summary", default="")
    done.add_argument("--fail", action="store_true")

    args = p.parse_args(argv)
    store = _store(args)

    if args.cmd == "create":
        rec = store.create(
            args.title,
            task_id=args.task_id,
            mode=args.mode,
            project_id=args.project,
            prompt=args.prompt,
        )
        print(json.dumps(rec.to_dict(), ensure_ascii=False, indent=2))
        return 0
    if args.cmd == "get":
        print(json.dumps(store.get(args.task_id).to_dict(), ensure_ascii=False, indent=2))
        return 0
    if args.cmd == "list":
        rows = [
            {"task_id": t.task_id, "title": t.title, "status": t.status, "mode": t.mode}
            for t in store.list_tasks(status=args.status)
        ]
        print(json.dumps(rows, ensure_ascii=False, indent=2))
        return 0
    if args.cmd == "status":
        rec = store.set_status(args.task_id, args.new_status)
        print(json.dumps(rec.to_dict(), ensure_ascii=False, indent=2))
        return 0
    if args.cmd == "append":
        rec = store.append_message(args.task_id, args.role, args.content)
        print(json.dumps({"task_id": rec.task_id, "messages": len(rec.messages)}, indent=2))
        return 0
    if args.cmd == "result":
        payload = json.loads(args.result_json)
        rec = store.add_result(args.task_id, payload)
        print(json.dumps({"task_id": rec.task_id, "results": len(rec.results)}, indent=2))
        return 0
    if args.cmd == "complete":
        rec = store.complete(args.task_id, summary=args.summary, ok=not args.fail)
        print(json.dumps(rec.to_dict(), ensure_ascii=False, indent=2))
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
