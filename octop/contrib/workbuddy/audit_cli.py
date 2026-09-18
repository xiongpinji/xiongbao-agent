# SPDX-License-Identifier: MIT
"""CLI: audit log emit / tail."""

from __future__ import annotations

import argparse
import json

from .audit import AuditLog


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="audit_cli")
    p.add_argument("--path", default="artifacts/audit/workbuddy.jsonl")
    sub = p.add_subparsers(dest="cmd", required=True)

    e = sub.add_parser("emit")
    e.add_argument("action")
    e.add_argument("--field", action="append", default=[], help="key=value")

    t = sub.add_parser("tail")
    t.add_argument("-n", type=int, default=20)

    args = p.parse_args(argv)
    log = AuditLog(args.path)
    if args.cmd == "emit":
        fields = {}
        for item in args.field or []:
            if "=" in item:
                k, v = item.split("=", 1)
                fields[k] = v
        rec = log.emit(args.action, **fields)
        print(json.dumps(rec, ensure_ascii=False, indent=2))
        return 0
    if args.cmd == "tail":
        print(json.dumps(log.read_tail(args.n), ensure_ascii=False, indent=2))
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
