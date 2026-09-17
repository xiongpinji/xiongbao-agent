#!/usr/bin/env python
# SPDX-License-Identifier: MIT
"""V1 deliverable verification: unit tests + smoke-50 bench.

Usage::

    python -S scripts/verify_v1.py
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(label: str, argv: list[str]) -> int:
    print("\n" + "=" * 60)
    print(f"▶ {label}")
    print("=" * 60)
    proc = subprocess.run(
        argv,
        cwd=str(ROOT),
        env={**dict(**{k: v for k, v in __import__("os").environ.items()}), "PYTHONPATH": str(ROOT)},
    )
    return int(proc.returncode)


def main() -> int:
    py = sys.executable
    steps = [
        ("converter unit tests", [py, "-S", "tests/contrib/workbuddy/run_tests.py"]),
        ("team runtime tests", [py, "-S", "tests/contrib/workbuddy/test_team_runtime.py"]),
        ("bench unit tests", [py, "-S", "tests/contrib/workbuddy/test_bench.py"]),
        ("local llm unit tests", [py, "-S", "tests/contrib/workbuddy/test_local_llm.py"]),
        (
            "smoke-50 bench",
            [
                py,
                "-S",
                "-m",
                "octop.contrib.workbuddy.bench.cli",
                "--sample",
                "50",
                "--out-dir",
                "artifacts/bench",
                "--list-office",
            ],
        ),
        ("stock partner demo", [py, "-S", "tests/contrib/workbuddy/demo_stock_partner.py"]),
        (
            "live local llm team",
            [
                py,
                "-S",
                "-m",
                "octop.contrib.workbuddy.team.live_cli",
                "--expert",
                "StockPartnerTeam",
                "--max-members",
                "2",
                "--max-tokens",
                "384",
                "--out",
                "artifacts/live_team/report.json",
            ],
        ),
    ]
    failed: list[str] = []
    for label, argv in steps:
        code = run(label, argv)
        if code != 0:
            failed.append(label)
            print(f"✗ {label} exit={code}")
        else:
            print(f"✓ {label}")

    print("\n" + "=" * 60)
    if failed:
        print(f"V1 VERIFY FAILED: {len(failed)} step(s): {', '.join(failed)}")
        return 1
    print("V1 VERIFY OK — deliverable ready")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
