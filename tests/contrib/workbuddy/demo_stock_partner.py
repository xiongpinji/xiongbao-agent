# SPDX-License-Identifier: MIT
"""Demo: StockPartnerTeam（腾讯自选股投研专家团）Supervisor dry-run + mock live.

Usage::

    python -S tests/contrib/workbuddy/demo_stock_partner.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT))

from octop.contrib.workbuddy.team.parser import write_team_artifacts  # noqa: E402
from octop.contrib.workbuddy.team.runtime import (  # noqa: E402
    MockMemberCaller,
    TeamAgentRuntime,
)

EXPERT = (
    PROJECT
    / "octop"
    / "src"
    / "octop"
    / "infra"
    / "agents"
    / "experts"
    / "library"
    / "StockPartnerTeam"
)


def main() -> int:
    if not (EXPERT / "SOUL.md").is_file():
        print(f"expert not found: {EXPERT}")
        return 1

    # Ensure team.json + agents/*.md exist
    write_team_artifacts(EXPERT)

    rt = TeamAgentRuntime.from_expert_dir(EXPERT, caller=MockMemberCaller())
    query = "帮我分析下茅台该不该买"

    print("=" * 60)
    print(f"Team: {rt.definition.expert_id}")
    print(f"Lead: {rt.definition.lead_id} / {rt.definition.lead_name}")
    print(f"Orchestration: {rt.definition.orchestration}")
    print(f"Members ({len(rt.definition.members)}):")
    for m in rt.definition.members:
        print(f"  - {m.emoji} {m.display_name} (`{m.agent_id}`) — {m.specialty[:40]}")
    print("=" * 60)

    dry = rt.run_sync(query, dry_run=True)
    print("\n[DRY-RUN PLAN]")
    print(json.dumps(dry.plan, ensure_ascii=False, indent=2))
    print(dry.final_report)

    live = rt.run_sync(query, dry_run=False)
    print("\n[MOCK LIVE]")
    print(live.summary())
    for o in live.member_outputs:
        print(f"\n--- member: {o.display_name} [{o.phase_id}] ---")
        print(o.content[:300])
    print("\n=== FINAL REPORT ===")
    print(live.final_report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
