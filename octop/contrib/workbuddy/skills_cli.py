# SPDX-License-Identifier: MIT
"""CLI for SkillHub (WorkBuddy skills runtime bind).

Examples::

    python -S -m octop.contrib.workbuddy.skills_cli list --limit 10
    python -S -m octop.contrib.workbuddy.skills_cli search --query diagnose
    python -S -m octop.contrib.workbuddy.skills_cli show --id diagnose
    python -S -m octop.contrib.workbuddy.skills_cli enable --id diagnose --id handoff
    python -S -m octop.contrib.workbuddy.skills_cli compose
    python -S -m octop.contrib.workbuddy.skills_cli run --id handoff --task "总结当前进度"
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .skills import SkillCatalog, SkillRuntime, default_builtin_skills_root
from .team.llm import OpenAICompatCaller


def _default_work() -> Path:
    return Path("artifacts") / "skillhub"


def _catalog(args: argparse.Namespace) -> SkillCatalog:
    root = Path(args.skills_root) if getattr(args, "skills_root", None) else None
    force_builtin = bool(getattr(args, "builtin", False))
    no_builtin = bool(getattr(args, "no_builtin", False))
    if root is not None:
        # Explicit override: builtin off unless --builtin
        include = force_builtin and not no_builtin
        return SkillCatalog(root, include_builtin=include)
    # Default vendor skills root: include builtin unless --no-builtin
    return SkillCatalog(include_builtin=not no_builtin)

def _runtime(args: argparse.Namespace, cat: SkillCatalog) -> SkillRuntime:
    work = Path(args.work_root)
    caller = None
    if getattr(args, "llm", False):
        llm = OpenAICompatCaller()
        caller = lambda system, user: llm.complete(system=system, user=user)  # noqa: E731
    return SkillRuntime(cat, work_root=work, llm_caller=caller)


def cmd_list(args: argparse.Namespace) -> int:
    cat = _catalog(args)
    n = cat.scan()
    items = cat.list()[: int(args.limit)]
    payload = {
        "skills_root": str(cat.skills_root),
        "extra_roots": [str(p) for p in cat.extra_roots],
        "include_builtin": cat.include_builtin,
        "builtin_root": str(default_builtin_skills_root()),
        "total": n,
        "showing": len(items),
        "skills": [
            {
                "id": m.id,
                "name": m.name,
                "description": (m.description_zh or m.description)[:160],
                "version": m.version,
            }
            for m in items
        ],
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def cmd_search(args: argparse.Namespace) -> int:
    cat = _catalog(args)
    hits = cat.search(args.query, limit=int(args.limit))
    print(
        json.dumps(
            {
                "query": args.query,
                "count": len(hits),
                "skills": [
                    {
                        "id": m.id,
                        "name": m.name,
                        "description": (m.description_zh or m.description)[:200],
                    }
                    for m in hits
                ],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def cmd_show(args: argparse.Namespace) -> int:
    cat = _catalog(args)
    try:
        pkg = cat.load(args.id)
    except KeyError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(json.dumps(pkg.to_dict(include_body=bool(args.full)), ensure_ascii=False, indent=2))
    return 0


def cmd_enable(args: argparse.Namespace) -> int:
    cat = _catalog(args)
    rt = _runtime(args, cat)
    enabled = []
    for sid in args.id:
        pkg = rt.enable(sid)
        enabled.append(pkg.meta.id)
    print(json.dumps({"enabled_now": rt.list_enabled(), "just_enabled": enabled}, ensure_ascii=False, indent=2))
    return 0


def cmd_disable(args: argparse.Namespace) -> int:
    cat = _catalog(args)
    rt = _runtime(args, cat)
    for sid in args.id:
        rt.disable(sid)
    print(json.dumps({"enabled": rt.list_enabled()}, ensure_ascii=False, indent=2))
    return 0


def cmd_compose(args: argparse.Namespace) -> int:
    cat = _catalog(args)
    rt = _runtime(args, cat)
    ids = args.id or None
    text = rt.compose_system(ids, max_chars=int(args.max_chars))
    out = {
        "enabled": rt.list_enabled() if ids is None else ids,
        "chars": len(text),
        "preview": text[:800],
    }
    if args.write:
        path = Path(args.work_root) / "COMPOSED_SYSTEM.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        out["wrote"] = str(path)
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    cat = _catalog(args)
    rt = _runtime(args, cat)
    row = rt.run(args.id, args.task, use_llm=bool(args.llm))
    print(json.dumps(row, ensure_ascii=False, indent=2))
    return 0 if row.get("ok") else 1


def cmd_scripts(args: argparse.Namespace) -> int:
    cat = _catalog(args)
    rt = _runtime(args, cat)
    try:
        scripts = rt.list_scripts(args.id)
    except KeyError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(json.dumps({"skill_id": args.id, "scripts": scripts}, ensure_ascii=False, indent=2))
    return 0


def cmd_exec(args: argparse.Namespace) -> int:
    cat = _catalog(args)
    rt = _runtime(args, cat)
    try:
        res = rt.run_script(
            args.id,
            args.script,
            args=list(args.arg or []),
            timeout_s=float(args.timeout),
            allow_net=bool(args.allow_net),
        )
    except KeyError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(json.dumps(res.to_dict(), ensure_ascii=False, indent=2))
    return 0 if res.ok else 1


def cmd_index(args: argparse.Namespace) -> int:
    cat = _catalog(args)
    cat.scan()
    path = Path(args.out) if args.out else Path(args.work_root) / "index.json"
    cat.write_index(path)
    print(json.dumps({"wrote": str(path), "total": len(cat.list())}, ensure_ascii=False, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="skills_cli", description="SkillHub runtime")
    p.add_argument("--skills-root", default=None, help="Override vendor skills dir")
    p.add_argument("--work-root", default=str(_default_work()))
    p.add_argument("--builtin", action="store_true", help="Force-include builtin-skills root")
    p.add_argument("--no-builtin", action="store_true", help="Exclude builtin-skills root")
    sub = p.add_subparsers(dest="cmd", required=True)

    def add_common(sp: argparse.ArgumentParser) -> None:
        sp.add_argument("--skills-root", default=None)
        sp.add_argument("--work-root", default=str(_default_work()))
        sp.add_argument("--builtin", action="store_true")
        sp.add_argument("--no-builtin", action="store_true")

    p_list = sub.add_parser("list", help="List skills")
    add_common(p_list)
    p_list.add_argument("--limit", type=int, default=30)
    p_list.set_defaults(func=cmd_list)

    p_search = sub.add_parser("search", help="Search by keyword")
    add_common(p_search)
    p_search.add_argument("--query", required=True)
    p_search.add_argument("--limit", type=int, default=20)
    p_search.set_defaults(func=cmd_search)

    p_show = sub.add_parser("show", help="Show one skill meta (+ body with --full)")
    add_common(p_show)
    p_show.add_argument("--id", required=True)
    p_show.add_argument("--full", action="store_true")
    p_show.set_defaults(func=cmd_show)

    p_en = sub.add_parser("enable", help="Enable skill(s) in work-root")
    add_common(p_en)
    p_en.add_argument("--id", action="append", required=True)
    p_en.set_defaults(func=cmd_enable)

    p_dis = sub.add_parser("disable", help="Disable skill(s)")
    add_common(p_dis)
    p_dis.add_argument("--id", action="append", required=True)
    p_dis.set_defaults(func=cmd_disable)

    p_comp = sub.add_parser("compose", help="Compose enabled skills into system prompt")
    add_common(p_comp)
    p_comp.add_argument("--id", action="append", default=None)
    p_comp.add_argument("--max-chars", type=int, default=14000)
    p_comp.add_argument("--write", action="store_true")
    p_comp.set_defaults(func=cmd_compose)

    p_run = sub.add_parser("run", help="Materialize pack; optional --llm invoke")
    add_common(p_run)
    p_run.add_argument("--id", required=True)
    p_run.add_argument("--task", required=True)
    p_run.add_argument("--llm", action="store_true")
    p_run.set_defaults(func=cmd_run)

    p_scripts = sub.add_parser("scripts", help="List allowlisted scripts under skill/scripts/")
    add_common(p_scripts)
    p_scripts.add_argument("--id", required=True)
    p_scripts.set_defaults(func=cmd_scripts)

    p_exec = sub.add_parser("exec", help="Run one allowlisted script (sandbox)")
    add_common(p_exec)
    p_exec.add_argument("--id", required=True)
    p_exec.add_argument("--script", required=True, help="Relative path under scripts/")
    p_exec.add_argument("--arg", action="append", default=[], help="Extra argv (repeatable)")
    p_exec.add_argument("--timeout", type=float, default=30.0)
    p_exec.add_argument("--allow-net", action="store_true")
    p_exec.set_defaults(func=cmd_exec)

    p_idx = sub.add_parser("index", help="Write JSON index of all skills")
    add_common(p_idx)
    p_idx.add_argument("--out", default=None)
    p_idx.set_defaults(func=cmd_index)
    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
