# SPDX-License-Identifier: MIT
"""CLI: soft enterprise probes (Casdoor / Milvus).

Examples::

    python -S -m octop.contrib.workbuddy.enterprise_cli probe
"""

from __future__ import annotations

import argparse
import json
import sys

from .enterprise import enterprise_probe


def cmd_probe(_args: argparse.Namespace) -> int:
    data = enterprise_probe()
    print(json.dumps(data, ensure_ascii=False, indent=2))
    # Soft probe never fails the process for unreachable optional services
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="enterprise_cli", description="Casdoor/Milvus soft probe")
    sub = p.add_subparsers(dest="cmd", required=True)
    pr = sub.add_parser("probe", help="Report env + optional reachability")
    pr.set_defaults(func=cmd_probe)
    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
