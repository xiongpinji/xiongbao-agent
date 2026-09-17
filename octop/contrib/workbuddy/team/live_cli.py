# SPDX-License-Identifier: MIT
"""CLI: run a team expert against a local OpenAI-compatible LLM.

Usage::

    python -S -m octop.contrib.workbuddy.team.live_cli \\
        --expert StockPartnerTeam \\
        --query "帮我分析下茅台该不该买" \\
        --max-members 2
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from .llm import OpenAICompatCaller
from .parser import write_team_artifacts
from .probe import chat_smoke, probe_local_llm
from .runtime import TeamAgentRuntime


def _default_library() -> Path:
    # …/octop/contrib/workbuddy/team/live_cli.py → parents[3] == …/octop
    return (
        Path(__file__).resolve().parents[3]
        / "src"
        / "octop"
        / "infra"
        / "agents"
        / "experts"
        / "library"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Live Team run on local LLM")
    parser.add_argument("--expert", default="StockPartnerTeam")
    parser.add_argument("--query", default="帮我分析下茅台该不该买")
    parser.add_argument("--library", type=Path, default=None)
    parser.add_argument("--base-url", default=None)
    parser.add_argument("--model", default=None)
    parser.add_argument("--max-members", type=int, default=2, help="Cap members for smoke speed")
    parser.add_argument("--max-tokens", type=int, default=512)
    parser.add_argument("--out", type=Path, default=Path("artifacts/live_team/report.json"))
    parser.add_argument("--probe-only", action="store_true")
    args = parser.parse_args(argv)

    probe = probe_local_llm(
        [args.base_url] if args.base_url else None,
    )
    print(json.dumps(probe.to_dict(), ensure_ascii=False, indent=2))
    if not probe.ok:
        print("FAIL: no local LLM endpoint reachable", file=sys.stderr)
        return 2

    model = args.model or probe.preferred_model
    base = args.base_url or probe.base_url
    print(f"smoke chat → {base} model={model}")
    try:
        smoke = chat_smoke(base_url=base, model=model)
        print(f"smoke reply: {smoke[:200]}")
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL: chat smoke: {exc}", file=sys.stderr)
        return 3

    if args.probe_only:
        return 0

    library = args.library or _default_library()
    expert_dir = library / args.expert
    if not (expert_dir / "SOUL.md").is_file():
        print(f"FAIL: expert not found: {expert_dir}", file=sys.stderr)
        return 4

    write_team_artifacts(expert_dir)
    caller = OpenAICompatCaller(
        base_url=base,
        model=model,
        max_tokens=args.max_tokens,
        temperature=0.2,
    )
    rt = TeamAgentRuntime.from_expert_dir(expert_dir, caller=caller)

    # Optionally shrink roster for local-model smoke
    if args.max_members > 0 and len(rt.definition.members) > args.max_members:
        kept = rt.definition.members[: args.max_members]
        rt.definition.members = kept
        for phase in rt.definition.phases:
            ids = [m.agent_id for m in kept if m.agent_id in phase.member_ids]
            # rebuild immutable-ish phase via object replace
            object.__setattr__(phase, "member_ids", tuple(ids))
        print(f"roster capped to {args.max_members}: {[m.agent_id for m in kept]}")

    t0 = time.perf_counter()
    print(f"running team={args.expert} query={args.query!r} …")
    result = rt.run_sync(args.query, dry_run=False)
    elapsed = time.perf_counter() - t0

    payload = {
        "expert": args.expert,
        "query": args.query,
        "base_url": base,
        "model": model,
        "elapsed_s": round(elapsed, 2),
        "caller_stats": {
            "calls": caller.stats.calls,
            "prompt_tokens": caller.stats.prompt_tokens,
            "completion_tokens": caller.stats.completion_tokens,
            "errors": caller.stats.errors,
        },
        "member_count": len(result.member_outputs),
        "members": [
            {
                "agent_id": o.agent_id,
                "display_name": o.display_name,
                "chars": len(o.content),
                "preview": o.content[:240],
            }
            for o in result.member_outputs
        ],
        "final_report": result.final_report,
        "plan": result.plan,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"elapsed={elapsed:.1f}s calls={caller.stats.calls}")
    print(f"final_report chars={len(result.final_report)}")
    print(result.final_report[:800])
    print(f"wrote {args.out}")

    # Acceptance: every member + lead returned non-trivial text
    ok_members = all(len(o.content) >= 20 for o in result.member_outputs)
    ok_final = len(result.final_report) >= 40
    if not (ok_members and ok_final and caller.stats.errors == 0):
        print("FAIL: live run quality gate", file=sys.stderr)
        return 5
    print("LIVE TEAM OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
