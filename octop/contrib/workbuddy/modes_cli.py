# SPDX-License-Identifier: MIT
"""CLI: assemble Ask / Plan / Craft system prompts (+ optional workspace memory).

Examples::

    python -S -m octop.contrib.workbuddy.modes_cli assemble --mode ask
    python -S -m octop.contrib.workbuddy.modes_cli assemble --mode craft --workspace .
    python -S -m octop.contrib.workbuddy.modes_cli check --mode plan
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .memory import load_workspace_memory
from .modes import (
    assemble_system_prompt,
    mode_allows_mutating_tools,
    mode_allows_writes,
    normalize_mode,
)


def cmd_assemble(args: argparse.Namespace) -> int:
    mode = normalize_mode(args.mode)
    soul = user = durable = daily = ""
    mem_info: dict = {}
    if args.workspace:
        mem = load_workspace_memory(args.workspace, max_chars=int(args.max_chars))
        soul, user, durable, daily = mem.soul, mem.user, mem.durable, mem.daily
        mem_info = mem.to_dict()
    expert_prompt = ""
    if args.expert_prompt and Path(args.expert_prompt).is_file():
        expert_prompt = Path(args.expert_prompt).read_text(encoding="utf-8", errors="replace")
    assembled = assemble_system_prompt(
        mode=mode,
        expert_prompt=expert_prompt,
        expert_id=args.expert_id or "",
        soul=soul,
        user_profile=user,
        working_memory=daily,
        durable_memory=durable,
        model_name=args.model or "local",
        extra=args.extra or "",
    )
    payload = {
        **assembled.to_dict(),
        "allows_writes": mode_allows_writes(mode),
        "allows_mutating_tools": mode_allows_mutating_tools(mode),
        "memory": mem_info,
        "system_chars": len(assembled.system),
        "system_preview": assembled.system[:600],
    }
    if args.write:
        out = Path(args.write)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(assembled.system, encoding="utf-8")
        payload["wrote"] = str(out)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def cmd_check(args: argparse.Namespace) -> int:
    mode = normalize_mode(args.mode)
    print(
        json.dumps(
            {
                "mode": mode,
                "allows_writes": mode_allows_writes(mode),
                "allows_mutating_tools": mode_allows_mutating_tools(mode),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="modes_cli", description="Ask/Plan/Craft assembler")
    sub = p.add_subparsers(dest="cmd", required=True)

    a = sub.add_parser("assemble", help="Build layered system prompt")
    a.add_argument("--mode", default="craft", help="ask | plan | craft")
    a.add_argument("--workspace", default=None, help="Dir with SOUL.md / USER.md / MEMORY.md")
    a.add_argument("--expert-prompt", default=None, help="Path to expert SOUL.md")
    a.add_argument("--expert-id", default="")
    a.add_argument("--model", default="local")
    a.add_argument("--extra", default="")
    a.add_argument("--max-chars", type=int, default=8000)
    a.add_argument("--write", default=None, help="Write full system prompt to path")
    a.set_defaults(func=cmd_assemble)

    c = sub.add_parser("check", help="Show mode write permissions")
    c.add_argument("--mode", default="ask")
    c.set_defaults(func=cmd_check)
    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
