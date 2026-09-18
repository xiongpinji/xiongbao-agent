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
import os
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
    parser.add_argument(
        "--skill",
        action="append",
        default=[],
        help="Bind SkillHub skill id(s) into the team prompt (repeatable)",
    )
    parser.add_argument(
        "--skills-work-root",
        type=Path,
        default=Path("artifacts/skillhub"),
        help="SkillRuntime work root for enable/compose state",
    )
    parser.add_argument(
        "--mode",
        default="craft",
        choices=["ask", "plan", "craft"],
        help="WorkBuddy work mode (ask=read-only, plan=plan-only, craft=full)",
    )
    parser.add_argument(
        "--workspace",
        type=Path,
        default=None,
        help="Workspace root for SOUL.md / USER.md / MEMORY.md injection",
    )
    args = parser.parse_args(argv)

    probe = probe_local_llm(
        [args.base_url] if args.base_url else None,
    )
    print(json.dumps(probe.to_dict(), ensure_ascii=False, indent=2))
    if not probe.ok:
        print("FAIL: no local LLM endpoint reachable", file=sys.stderr)
        return 2

    # Priority: --model > WB_LLM_MODEL > probe preferred (often smallest)
    model = args.model or os.environ.get("WB_LLM_MODEL") or probe.preferred_model
    base = args.base_url or os.environ.get("WB_LLM_BASE_URL") or probe.base_url
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
    query = args.query
    bound_skills: list[str] = []
    if args.skill:
        from ..skills import SkillCatalog, SkillRuntime

        sk_cat = SkillCatalog()
        sk_rt = SkillRuntime(sk_cat, work_root=args.skills_work_root)
        for sid in args.skill:
            sk_rt.enable(sid)
            bound_skills.append(sid)
        composed = sk_rt.compose_system(bound_skills, max_chars=8000)
        if composed:
            query = (
                "[Bound Skills — follow their procedures when relevant]\n"
                f"{composed}\n\n"
                f"[User request]\n{args.query}"
            )
            print(f"bound skills: {bound_skills} ({len(composed)} chars)")

    # Modes + workspace memory (WorkBuddy parity)
    from ..memory import load_workspace_memory
    from ..modes import assemble_system_prompt, mode_allows_writes, normalize_mode

    work_mode = normalize_mode(args.mode)
    soul = user = durable = daily = ""
    if args.workspace:
        mem = load_workspace_memory(args.workspace)
        soul, user, durable, daily = mem.soul, mem.user, mem.durable, mem.daily
        print(f"workspace memory: {mem.to_dict()}")
    expert_soul = ""
    soul_path = expert_dir / "SOUL.md"
    if soul_path.is_file():
        expert_soul = soul_path.read_text(encoding="utf-8", errors="replace")[:6000]
    assembled = assemble_system_prompt(
        mode=work_mode,
        expert_prompt=expert_soul,
        expert_id=args.expert,
        soul=soul,
        user_profile=user,
        working_memory=daily,
        durable_memory=durable,
        model_name=str(model or "local"),
    )
    # Inject mode gate + memory into the user turn (Team runtime owns member SOULs)
    mode_prefix = (
        f"[Work mode: {work_mode} | writes={'yes' if mode_allows_writes(work_mode) else 'no'}]\n"
        f"{assembled.sections[-1]}\n\n"
    )
    mem_bits = []
    if soul.strip():
        mem_bits.append("## SOUL.md\n" + soul.strip()[:2000])
    if user.strip():
        mem_bits.append("## USER.md\n" + user.strip()[:2000])
    if durable.strip():
        mem_bits.append("## MEMORY.md\n" + durable.strip()[:2000])
    if daily.strip():
        mem_bits.append("## Daily memory\n" + daily.strip()[:2000])
    if mem_bits:
        mode_prefix += "[Workspace identity]\n" + "\n\n".join(mem_bits) + "\n\n"
    if work_mode == "ask":
        mode_prefix += (
            "[Ask gate] Answer only; do not propose file edits or shell mutations.\n\n"
        )
    elif work_mode == "plan":
        mode_prefix += (
            "[Plan gate] Produce an ordered plan with acceptance checks; "
            "do not execute irreversible steps.\n\n"
        )
    query = mode_prefix + query
    print(f"mode={work_mode} system_chars={len(assembled.system)}")

    print(f"running team={args.expert} query={args.query!r} …")
    result = rt.run_sync(query, dry_run=False)
    elapsed = time.perf_counter() - t0

    payload = {
        "expert": args.expert,
        "query": args.query,
        "mode": work_mode,
        "bound_skills": bound_skills,
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
