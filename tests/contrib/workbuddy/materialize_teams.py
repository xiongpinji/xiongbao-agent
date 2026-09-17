# SPDX-License-Identifier: MIT
"""Materialize team.json + agents/*.md for all team experts already in library."""

from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT))

from octop.contrib.workbuddy.team.parser import (  # noqa: E402
    parse_team_soul,
    write_team_artifacts,
)


def main() -> int:
    library = PROJECT / "octop" / "src" / "octop" / "infra" / "agents" / "experts" / "library"
    if not library.is_dir():
        print(f"library not found: {library}")
        return 1

    teams: list[Path] = []
    for d in sorted(library.iterdir()):
        if not d.is_dir():
            continue
        mf = d / "manifest.json"
        if not mf.is_file():
            continue
        try:
            data = json.loads(mf.read_text(encoding="utf-8"))
        except Exception:
            continue
        wb = data.get("_wb") or {}
        if wb.get("expert_type") == "team" or d.name.endswith("Team"):
            teams.append(d)

    print(f"found {len(teams)} team expert dirs")
    ok = 0
    empty = 0
    for d in teams:
        soul = d / "SOUL.md"
        if not soul.is_file():
            print(f"SKIP {d.name}: no SOUL.md")
            continue
        definition = parse_team_soul(
            soul.read_text(encoding="utf-8"),
            expert_id=d.name,
            source=str(soul),
        )
        try:
            write_team_artifacts(d, definition)
        except PermissionError as exc:
            print(f"LOCK {d.name}: {exc}")
            continue
        n = len(definition.members)
        if n == 0:
            empty += 1
            print(f"WARN {d.name}: 0 members parsed (lead={definition.lead_id})")
        else:
            ok += 1
            print(
                f"OK   {d.name}: {n} members / {len(definition.phases)} phase(s) "
                f"[{definition.orchestration}] lead={definition.lead_id}"
            )

    print(f"\ndone: {ok} with roster, {empty} empty, {len(teams)} total")
    return 0 if empty < len(teams) else 1


if __name__ == "__main__":
    raise SystemExit(main())
