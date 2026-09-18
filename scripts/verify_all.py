#!/usr/bin/env python
# SPDX-License-Identifier: MIT
"""One-shot WorkBuddy parity verification (V1–V6 core, no live LLM required).

Usage::

    python -S scripts/verify_all.py
    python -S scripts/verify_all.py --live   # optional Ollama office lite
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(label: str, argv: list[str]) -> int:
    print("\n" + "=" * 60)
    print(f"▶ {label}")
    print("=" * 60)
    env = dict(os.environ)
    env["PYTHONPATH"] = str(ROOT)
    proc = subprocess.run(argv, cwd=str(ROOT), env=env)
    return int(proc.returncode)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify WorkBuddy stack end-to-end")
    parser.add_argument("--live", action="store_true", help="Include live office llm_lite")
    parser.add_argument("--limit", type=int, default=2)
    parser.add_argument("--pass-rate", type=float, default=0.0)
    args = parser.parse_args(argv)
    py = sys.executable

    steps: list[tuple[str, list[str]]] = [
        ("converter unit", [py, "-S", "tests/contrib/workbuddy/run_tests.py"]),
        ("team runtime unit", [py, "-S", "tests/contrib/workbuddy/test_team_runtime.py"]),
        ("bench unit", [py, "-S", "tests/contrib/workbuddy/test_bench.py"]),
        ("skillhub unit", [py, "-S", "tests/contrib/workbuddy/test_skillhub.py"]),
        ("goal craft unit", [py, "-S", "tests/contrib/workbuddy/test_goal_craft.py"]),
        ("v6 modes/memory/router", [py, "-S", "tests/contrib/workbuddy/test_v6_modes_memory_router.py"]),
        (
            "modes assemble ask",
            [py, "-S", "-m", "octop.contrib.workbuddy.modes_cli", "assemble", "--mode", "ask"],
        ),
        (
            "connectors probe",
            [py, "-S", "-m", "octop.contrib.workbuddy.connectors_cli", "probe"],
        ),
        (
            "connectors list",
            [
                py,
                "-S",
                "-m",
                "octop.contrib.workbuddy.connectors_cli",
                "list",
                "--limit",
                "5",
            ],
        ),
        (
            "router sample",
            [
                py,
                "-S",
                "-m",
                "octop.contrib.workbuddy.router_cli",
                "route",
                "--query",
                "股票",
                "--limit",
                "3",
            ],
        ),
        (
            "skills list (builtin)",
            [py, "-S", "-m", "octop.contrib.workbuddy.skills_cli", "list", "--limit", "5"],
        ),
        (
            "enterprise probe",
            [py, "-S", "-m", "octop.contrib.workbuddy.enterprise_cli", "probe"],
        ),
        (
            "bench list subsets",
            [
                py,
                "-S",
                "-m",
                "octop.contrib.workbuddy.bench.cli",
                "--list-subsets",
                "--dry-sample-only",
                "--out-dir",
                "artifacts/bench_verify_all",
            ],
        ),
        (
            "goal plan-only (ask mode)",
            [
                py,
                "-S",
                "-m",
                "octop.contrib.workbuddy.goal_cli",
                "plan",
                "--goal",
                "写一份周报",
                "--work-mode",
                "ask",
                "--root",
                "artifacts/goal_verify_all",
            ],
        ),
        ("v8 production unit", [py, "-S", "tests/contrib/workbuddy/test_v8_production.py"]),
        (
            "hub status",
            [py, "-S", "-m", "octop.contrib.workbuddy.hub_cli", "status"],
        ),
    ]

    if args.live:
        steps.append(
            (
                "office llm_lite live",
                [
                    py,
                    "-S",
                    "-m",
                    "octop.contrib.workbuddy.bench.cli",
                    "--office",
                    "--live-llm",
                    "--limit",
                    str(args.limit),
                    "--pass-rate",
                    str(args.pass_rate),
                    "--out-dir",
                    "artifacts/bench_verify_all_live",
                ],
            )
        )

    failed: list[str] = []
    for label, cmd in steps:
        code = run(label, cmd)
        if code != 0:
            failed.append(label)
            print(f"✗ {label} exit={code}")
        else:
            print(f"✓ {label}")

    # Required packaging / board files
    required = [
        ROOT / "TASKBOARD.md",
        ROOT / "ROADMAP.md",
        ROOT / "scripts" / "fetch_bench_subsets.ps1",
        ROOT / "octop" / "contrib" / "workbuddy" / "modes" / "assembler.py",
        ROOT / "octop" / "contrib" / "workbuddy" / "memory" / "loader.py",
        ROOT / "octop" / "contrib" / "workbuddy" / "router" / "expert_router.py",
        ROOT / "octop" / "contrib" / "workbuddy" / "connectors" / "extended.py",
        ROOT / "octop" / "contrib" / "workbuddy" / "enterprise" / "probe.py",
    ]
    print("\n" + "=" * 60)
    print("▶ packaging files")
    print("=" * 60)
    for path in required:
        if path.is_file():
            print(f"✓ {path.relative_to(ROOT)}")
        else:
            print(f"✗ missing {path.relative_to(ROOT)}")
            failed.append(f"missing:{path.name}")

    print("\n" + "=" * 60)
    if failed:
        print(f"VERIFY ALL FAILED ({len(failed)}): {', '.join(failed)}")
        return 1
    print("VERIFY ALL OK — WorkBuddy V8 production path green")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
