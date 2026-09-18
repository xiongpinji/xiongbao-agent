# SPDX-License-Identifier: MIT
"""CLI for V10 runtime wiring."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .runtime import (
    apply_profile_env,
    check_run_allowed,
    create_task_with_worktree,
    export_parity_bundle,
    import_parity_bundle,
    kb_prompt_prefix,
    publish_cowrite_to_library,
    register_installed_skill,
    run_task,
)
from .runtime.inbox_poll import make_default_poller


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="runtime_cli", description="V10 runtime wiring")
    sub = p.add_subparsers(dest="cmd", required=True)

    tr = sub.add_parser("run-task", help="Run task via GoalEngine")
    tr.add_argument("--task-id", required=True)
    tr.add_argument("--tasks-root", default="artifacts/tasks")
    tr.add_argument("--goals-root", default="artifacts/goal_craft")
    tr.add_argument("--policy", default="artifacts/security/policy.json")
    tr.add_argument("--kb-root", default="artifacts/knowledge")
    tr.add_argument("--live", action="store_true")
    tr.add_argument("--approve-all", action="store_true", default=True)

    pg = sub.add_parser("policy-check")
    pg.add_argument("--mode", default="craft")
    pg.add_argument("--policy", default="artifacts/security/policy.json")
    pg.add_argument("--write", action="store_true", default=True)
    pg.add_argument("--shell", action="store_true")

    pe = sub.add_parser("profile-apply")
    pe.add_argument("--path", default="artifacts/models/profiles.json")

    ip = sub.add_parser("inbox-poll")
    ip.add_argument("--inbox", default="artifacts/china_im/inbox.jsonl")
    ip.add_argument("--tasks-root", default="artifacts/tasks")
    ip.add_argument("--allow", action="store_true")
    ip.add_argument("--limit", type=int, default=20)

    sr = sub.add_parser("skill-register")
    sr.add_argument("--id", dest="skill_id", default="")
    sr.add_argument("--source", default="")
    sr.add_argument("--dest", default="artifacts/skillhub/installed")
    sr.add_argument("--force", action="store_true")

    kb = sub.add_parser("kb-prefix")
    kb.add_argument("--root", default="artifacts/knowledge")
    kb.add_argument("--query", required=True)

    be = sub.add_parser("bundle-export")
    be.add_argument("--artifacts", default="artifacts")
    be.add_argument("--out", required=True)

    bi = sub.add_parser("bundle-import")
    bi.add_argument("--archive", required=True)
    bi.add_argument("--artifacts", default="artifacts")

    tw = sub.add_parser("task-worktree")
    tw.add_argument("--title", required=True)
    tw.add_argument("--tasks-root", default="artifacts/tasks")
    tw.add_argument("--prompt", default="")
    tw.add_argument("--with-worktree", action="store_true")
    tw.add_argument("--live-wt", action="store_true", help="actually create git worktree")

    cp = sub.add_parser("cowrite-publish")
    cp.add_argument("--session-id", required=True)
    cp.add_argument("--cowrite-root", default="artifacts/cowrite")
    cp.add_argument("--library-root", default="artifacts/library")

    args = p.parse_args(argv)

    if args.cmd == "run-task":
        result = run_task(
            args.task_id,
            tasks_root=args.tasks_root,
            goals_root=args.goals_root,
            policy_path=args.policy,
            kb_root=args.kb_root,
            dry_run=not args.live,
            approve_all=args.approve_all,
        )
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
        return 0 if result.ok else 1

    if args.cmd == "policy-check":
        d = check_run_allowed(
            mode=args.mode,
            policy_path=args.policy,
            needs_write=args.write,
            needs_shell=args.shell,
        )
        print(json.dumps(d.to_dict(), ensure_ascii=False, indent=2))
        return 0 if d.allowed else 2

    if args.cmd == "profile-apply":
        print(json.dumps(apply_profile_env(path=args.path), ensure_ascii=False, indent=2))
        return 0

    if args.cmd == "inbox-poll":
        poller = make_default_poller(
            inbox_path=args.inbox,
            tasks_root=args.tasks_root,
            allow=args.allow,
        )
        print(json.dumps(poller.poll(limit=args.limit), ensure_ascii=False, indent=2))
        return 0

    if args.cmd == "skill-register":
        if not args.skill_id and not args.source:
            print(json.dumps({"error": "need --id or --source"}, ensure_ascii=False))
            return 2
        out = register_installed_skill(
            args.source or None,
            skill_id=args.skill_id or None,
            dest_root=args.dest,
            force=args.force,
        )
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return 0 if out.get("registered") else 1

    if args.cmd == "kb-prefix":
        print(kb_prompt_prefix(args.root, args.query) or "(no hits)")
        return 0

    if args.cmd == "bundle-export":
        print(json.dumps(export_parity_bundle(args.artifacts, args.out), ensure_ascii=False, indent=2))
        return 0

    if args.cmd == "bundle-import":
        print(
            json.dumps(
                import_parity_bundle(args.archive, args.artifacts),
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0

    if args.cmd == "task-worktree":
        out = create_task_with_worktree(
            args.title,
            tasks_root=args.tasks_root,
            prompt=args.prompt,
            with_worktree=args.with_worktree,
            dry_run=not args.live_wt,
        )
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return 0

    if args.cmd == "cowrite-publish":
        print(
            json.dumps(
                publish_cowrite_to_library(
                    args.session_id,
                    cowrite_root=args.cowrite_root,
                    library_root=args.library_root,
                ),
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
