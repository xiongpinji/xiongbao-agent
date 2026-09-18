#!/usr/bin/env python
# SPDX-License-Identifier: MIT
"""V4 deliverable verification: skillhub sandbox / goal+skills / connectors outbox.

Usage::

    python -S scripts/verify_v4.py
"""

from __future__ import annotations

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


def main() -> int:
    py = sys.executable
    steps = [
        ("skillhub (+ script sandbox)", [py, "-S", "tests/contrib/workbuddy/test_skillhub.py"]),
        ("goal/craft (+ --skill bind)", [py, "-S", "tests/contrib/workbuddy/test_goal_craft.py"]),
        ("connectors + outbox retry", [py, "-S", "tests/contrib/workbuddy/test_connectors_replay.py"]),
        ("teach/routine", [py, "-S", "tests/contrib/workbuddy/test_teach_routine.py"]),
        (
            "goal_cli plan --skill smoke",
            [
                py,
                "-S",
                "-m",
                "octop.contrib.workbuddy.goal_cli",
                "plan",
                "--goal",
                "写入 v4-smoke.md",
                "--root",
                "artifacts/goal_craft_v4",
            ],
        ),
        (
            "skills_cli list smoke",
            [
                py,
                "-S",
                "-m",
                "octop.contrib.workbuddy.skills_cli",
                "list",
                "--limit",
                "3",
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
        print(f"V4 VERIFY FAILED: {len(failed)} step(s): {', '.join(failed)}")
        return 1
    print("V4 VERIFY OK — sandbox / goal--skill / outbox retry ready")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
