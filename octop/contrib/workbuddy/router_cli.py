# SPDX-License-Identifier: MIT
"""CLI: expert auto-router.

Examples::

    python -S -m octop.contrib.workbuddy.router_cli route --query "股票分析"
    python -S -m octop.contrib.workbuddy.router_cli route --query "育儿" --kind agent --limit 5
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .router import ExpertRouter


def cmd_route(args: argparse.Namespace) -> int:
    router = ExpertRouter(Path(args.library) if args.library else None)
    n = router.load()
    hits = router.route(args.query, limit=int(args.limit), kind=args.kind)
    print(
        json.dumps(
            {
                "library": str(router.library),
                "experts_indexed": n,
                "query": args.query,
                "kind": args.kind,
                "hits": [h.to_dict() for h in hits],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if hits else 1


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="router_cli", description="Expert auto-router")
    sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("route", help="Match query to library experts")
    r.add_argument("--query", required=True)
    r.add_argument("--library", default=None)
    r.add_argument("--kind", default=None, choices=["agent", "team", "plugin"])
    r.add_argument("--limit", type=int, default=5)
    r.set_defaults(func=cmd_route)
    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
