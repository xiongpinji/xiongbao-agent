# SPDX-License-Identifier: MIT
"""CLI: connector catalog + probe (Notion / Feishu / DingTalk / WeCom).

Examples::

    python -S -m octop.contrib.workbuddy.connectors_cli probe
    python -S -m octop.contrib.workbuddy.connectors_cli list --limit 20
    python -S -m octop.contrib.workbuddy.connectors_cli search --query notion
    python -S -m octop.contrib.workbuddy.connectors_cli show --id notion
"""

from __future__ import annotations

import argparse
import json
import sys

from .connectors import probe_status
from .connectors.extended import ConnectorCatalog, load_mcp_json


def cmd_probe(_args: argparse.Namespace) -> int:
    print(json.dumps(probe_status(), ensure_ascii=False, indent=2))
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    cat = ConnectorCatalog()
    n = cat.scan()
    items = cat.list()[: int(args.limit)]
    print(
        json.dumps(
            {
                "root": str(cat.root),
                "total": n,
                "showing": len(items),
                "connectors": [c.to_dict() for c in items],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def cmd_search(args: argparse.Namespace) -> int:
    cat = ConnectorCatalog()
    hits = cat.search(args.query, limit=int(args.limit))
    print(
        json.dumps(
            {"query": args.query, "count": len(hits), "connectors": [c.to_dict() for c in hits]},
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def cmd_show(args: argparse.Namespace) -> int:
    cat = ConnectorCatalog()
    cat.scan()
    hit = next((c for c in cat.list() if c.id == args.id), None)
    if hit is None:
        print(json.dumps({"error": f"not found: {args.id}"}, ensure_ascii=False), file=sys.stderr)
        return 2
    mcp = load_mcp_json(args.id) if args.mcp else None
    print(
        json.dumps(
            {"meta": hit.to_dict(), "mcp": mcp},
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="connectors_cli", description="Connector catalog / probe")
    sub = p.add_subparsers(dest="cmd", required=True)

    p_probe = sub.add_parser("probe", help="Env + outbound readiness")
    p_probe.set_defaults(func=cmd_probe)

    p_list = sub.add_parser("list", help="List vendor connector packages")
    p_list.add_argument("--limit", type=int, default=30)
    p_list.set_defaults(func=cmd_list)

    p_search = sub.add_parser("search", help="Search connector id")
    p_search.add_argument("--query", required=True)
    p_search.add_argument("--limit", type=int, default=30)
    p_search.set_defaults(func=cmd_search)

    p_show = sub.add_parser("show", help="Show one connector package")
    p_show.add_argument("--id", required=True)
    p_show.add_argument("--mcp", action="store_true", help="Include mcp.json if present")
    p_show.set_defaults(func=cmd_show)
    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
