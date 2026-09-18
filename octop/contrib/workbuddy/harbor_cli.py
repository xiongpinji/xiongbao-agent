# SPDX-License-Identifier: MIT
"""CLI: Harbor / Docker bridge for WorkBuddy Bench."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from .bench.harbor import (
    docker_build_smoke,
    harbor_bridge_report,
    harbor_dry_run,
    harbor_status,
    list_tasks,
    uv_sync_bench,
    validate_task,
)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="harbor_cli", description="Harbor Docker bridge")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("status", help="Docker / dataset / Python readiness")
    s.set_defaults(func=lambda a: print(json.dumps(harbor_status().to_dict(), ensure_ascii=False, indent=2)) or 0)

    r = sub.add_parser("report", help="Status + validate sample tasks")
    r.add_argument("--subset", default="office")
    r.add_argument("--limit", type=int, default=3)
    r.set_defaults(
        func=lambda a: print(
            json.dumps(
                harbor_bridge_report(subset=a.subset, limit=a.limit),
                ensure_ascii=False,
                indent=2,
            )
        )
        or 0
    )

    l = sub.add_parser("list", help="List tasks in a subset")
    l.add_argument("--subset", default="office")
    l.add_argument("--limit", type=int, default=20)
    l.set_defaults(
        func=lambda a: print(json.dumps(list_tasks(a.subset, limit=a.limit), ensure_ascii=False, indent=2))
        or 0
    )

    v = sub.add_parser("validate", help="Validate one task directory")
    v.add_argument("task_dir")
    v.set_defaults(
        func=lambda a: print(json.dumps(validate_task(Path(a.task_dir)), ensure_ascii=False, indent=2))
        or (0 if validate_task(Path(a.task_dir))["ok"] else 1)
    )

    b = sub.add_parser("build-smoke", help="docker build one task environment")
    b.add_argument("--subset", default="office")
    b.add_argument("--task", default="", help="Task id; default first valid task")
    b.add_argument("--timeout", type=float, default=600.0)
    b.set_defaults(func=_cmd_build_smoke)

    sync = sub.add_parser("sync", help="uv sync vendor/workbuddy-bench (.venv)")
    sync.add_argument("--python", default="3.12")
    sync.set_defaults(func=_cmd_sync)

    dr = sub.add_parser("dry-run", help="Official Harbor dry-run (manifest resolve)")
    dr.add_argument("--job", default="local-openai-cbc-office-smoke")
    dr.set_defaults(func=_cmd_dry_run)

    args = p.parse_args(argv)
    return int(args.func(args))


def _cmd_sync(args: argparse.Namespace) -> int:
    result = uv_sync_bench(python=args.python)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("ok") else 1


def _cmd_dry_run(args: argparse.Namespace) -> int:
    result = harbor_dry_run(job=args.job)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("ok") else 1


def _cmd_build_smoke(args: argparse.Namespace) -> int:
    if os.environ.get("WB_HARBOR_SKIP_BUILD") in {"1", "true", "yes"}:
        print(json.dumps({"ok": True, "skipped": True, "reason": "WB_HARBOR_SKIP_BUILD"}, indent=2))
        return 0
    tasks = list_tasks(args.subset, limit=50)
    task_path = None
    if args.task:
        for t in tasks:
            if t["task_id"] == args.task:
                task_path = Path(t["path"])
                break
        if task_path is None:
            print(json.dumps({"ok": False, "error": f"task not found: {args.task}"}, indent=2))
            return 1
    else:
        for t in tasks:
            if t.get("has_dockerfile"):
                task_path = Path(t["path"])
                break
    if task_path is None:
        print(json.dumps({"ok": False, "error": "no task with Dockerfile"}, indent=2))
        return 1
    result = docker_build_smoke(task_path, timeout=float(args.timeout))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
