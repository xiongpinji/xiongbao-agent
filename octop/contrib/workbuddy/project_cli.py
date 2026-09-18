# SPDX-License-Identifier: MIT
"""CLI: project space (shared workspace + skill deposit)."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .project import ProjectSpace


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="project_cli")
    p.add_argument("--root", default="artifacts/projects", help="Projects root directory")
    sub = p.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("create")
    c.add_argument("project_id")
    c.add_argument("--name", default="")
    c.add_argument("--member", action="append", default=[])
    c.add_argument("--description", default="")

    ls = sub.add_parser("list")

    sh = sub.add_parser("show")
    sh.add_argument("project_id")

    dep = sub.add_parser("deposit-skill")
    dep.add_argument("project_id")
    dep.add_argument("skill_path")

    sk = sub.add_parser("list-skills")
    sk.add_argument("project_id")

    wr = sub.add_parser("write-shared")
    wr.add_argument("project_id")
    wr.add_argument("relative")
    wr.add_argument("--text", default="")
    wr.add_argument("--file", default="")

    args = p.parse_args(argv)
    space = ProjectSpace(args.root)

    if args.cmd == "create":
        meta = space.create(
            args.project_id,
            name=args.name,
            members=list(args.member or []),
            description=args.description,
        )
        print(json.dumps(meta.to_dict(), ensure_ascii=False, indent=2))
        return 0
    if args.cmd == "list":
        print(
            json.dumps([m.to_dict() for m in space.list_projects()], ensure_ascii=False, indent=2)
        )
        return 0
    if args.cmd == "show":
        print(json.dumps(space.load(args.project_id).to_dict(), ensure_ascii=False, indent=2))
        return 0
    if args.cmd == "deposit-skill":
        dest = space.deposit_skill(args.project_id, args.skill_path)
        print(json.dumps({"ok": True, "path": str(dest)}, ensure_ascii=False, indent=2))
        return 0
    if args.cmd == "list-skills":
        print(json.dumps({"skills": space.list_skills(args.project_id)}, ensure_ascii=False, indent=2))
        return 0
    if args.cmd == "write-shared":
        text = args.text
        if args.file:
            text = Path(args.file).read_text(encoding="utf-8")
        path = space.write_shared(args.project_id, args.relative, text)
        print(json.dumps({"ok": True, "path": str(path)}, ensure_ascii=False, indent=2))
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
