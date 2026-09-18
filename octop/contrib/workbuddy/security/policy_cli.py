# SPDX-License-Identifier: MIT
"""CLI for security policy."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from . import MODES, PolicyStore, SecurityPolicy


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="policy_cli")
    p.add_argument("--path", default="artifacts/security/policy.json")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("get")
    s = sub.add_parser("set")
    s.add_argument("--mode", choices=list(MODES), default=None)
    s.add_argument("--allow-outbound", type=int, choices=[0, 1], default=None)
    s.add_argument("--allow-shell", type=int, choices=[0, 1], default=None)
    s.add_argument("--allow-write", type=int, choices=[0, 1], default=None)
    c = sub.add_parser("check-tool")
    c.add_argument("tool")
    args = p.parse_args(argv)
    store = PolicyStore(args.path)

    if args.cmd == "get":
        print(json.dumps(store.load().to_dict(), ensure_ascii=False, indent=2))
        return 0
    if args.cmd == "set":
        fields: dict = {}
        if args.mode is not None:
            fields["default_mode"] = args.mode
        if args.allow_outbound is not None:
            fields["allow_outbound"] = bool(args.allow_outbound)
        if args.allow_shell is not None:
            fields["allow_shell"] = bool(args.allow_shell)
        if args.allow_write is not None:
            fields["allow_filesystem_write"] = bool(args.allow_write)
        if not fields:
            fields = SecurityPolicy().to_dict()
            store.save(SecurityPolicy())
        else:
            store.update(**fields)
        print(json.dumps(store.load().to_dict(), ensure_ascii=False, indent=2))
        return 0
    if args.cmd == "check-tool":
        pol = store.load()
        ok = pol.allows_tool(args.tool)
        print(json.dumps({"tool": args.tool, "allowed": ok}, indent=2))
        return 0 if ok else 2
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
