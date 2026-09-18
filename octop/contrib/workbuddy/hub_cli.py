# SPDX-License-Identifier: MIT
"""CLI: WorkBuddy hub — one-stop status / harbor / compose hints."""

from __future__ import annotations

import argparse
import json

from .bench.harbor import harbor_dry_run, harbor_status, uv_sync_bench
from .hub import hub_status


def _cmd_sync(args: argparse.Namespace) -> int:
    result = uv_sync_bench(python=args.python)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("ok") else 1


def _cmd_dry_run(args: argparse.Namespace) -> int:
    result = harbor_dry_run(job=args.job)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("ok") else 1


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="hub_cli", description="WorkBuddy production hub")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("status", help="Aggregate harbor + enterprise + audit")
    s.set_defaults(func=lambda _a: print(json.dumps(hub_status(), ensure_ascii=False, indent=2)) or 0)

    h = sub.add_parser("harbor", help="Harbor readiness only")
    h.set_defaults(func=lambda _a: print(json.dumps(harbor_status().to_dict(), ensure_ascii=False, indent=2)) or 0)

    sync = sub.add_parser("sync", help="uv sync vendor/workbuddy-bench")
    sync.add_argument("--python", default="3.12")
    sync.set_defaults(func=_cmd_sync)

    dr = sub.add_parser("dry-run", help="Harbor official dry-run (office smoke job)")
    dr.add_argument("--job", default="local-openai-cbc-office-smoke")
    dr.set_defaults(func=_cmd_dry_run)

    args = p.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
