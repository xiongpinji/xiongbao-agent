# SPDX-License-Identifier: MIT
"""CLI for git worktree parallel tasks."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .gitwork import WorktreeManager


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="worktree_cli")
    p.add_argument("--repo", default=".")
    p.add_argument("--registry", default=None)
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list")
    c = sub.add_parser("create")
    c.add_argument("--path", required=True)
    c.add_argument("--branch", required=True)
    c.add_argument("--task-id", default="")
    c.add_argument("--dry-run", action="store_true")
    r = sub.add_parser("remove")
    r.add_argument("--path", required=True)
    r.add_argument("--dry-run", action="store_true")
    r.add_argument("--force", action="store_true")
    args = p.parse_args(argv)
    mgr = WorktreeManager(args.repo, args.registry)
    if args.cmd == "list":
        print(json.dumps([x.to_dict() for x in mgr.list()], ensure_ascii=False, indent=2))
        return 0
    if args.cmd == "create":
        info = mgr.create(args.path, args.branch, task_id=args.task_id, dry_run=args.dry_run)
        print(json.dumps(info.to_dict(), ensure_ascii=False, indent=2))
        return 0
    if args.cmd == "remove":
        ok = mgr.remove(args.path, dry_run=args.dry_run, force=args.force)
        print(json.dumps({"removed": ok, "path": args.path}, indent=2))
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
