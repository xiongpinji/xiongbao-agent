# SPDX-License-Identifier: MIT
"""CLI for workspace export/import."""

from __future__ import annotations

import argparse
import json

from .data import export_workspace, import_workspace


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="data_cli")
    sub = p.add_subparsers(dest="cmd", required=True)
    e = sub.add_parser("export")
    e.add_argument("--source", required=True)
    e.add_argument("--archive", required=True)
    i = sub.add_parser("import")
    i.add_argument("--archive", required=True)
    i.add_argument("--dest", required=True)
    i.add_argument("--overwrite", action="store_true")
    args = p.parse_args(argv)
    if args.cmd == "export":
        print(json.dumps(export_workspace(args.source, args.archive), ensure_ascii=False, indent=2))
        return 0
    if args.cmd == "import":
        print(
            json.dumps(
                import_workspace(args.archive, args.dest, overwrite=args.overwrite),
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
