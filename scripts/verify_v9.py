#!/usr/bin/env python
# SPDX-License-Identifier: MIT
"""Verify V9 remaining WorkBuddy parity.

Usage::

    python -S scripts/verify_v9.py
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


def main(argv: list[str] | None = None) -> int:
    py = sys.executable
    steps: list[tuple[str, list[str]]] = [
        ("v9 unit tests", [py, "-S", "tests/contrib/workbuddy/test_v9_remaining.py"]),
        ("hub status v9", [py, "-S", "-m", "octop.contrib.workbuddy.hub_cli", "status"]),
        (
            "task lifecycle",
            [
                py,
                "-S",
                "-m",
                "octop.contrib.workbuddy.task_cli",
                "--root",
                "artifacts/tasks_verify_v9",
                "create",
                "--title",
                "verify-v9",
                "--id",
                "verify-v9-smoke",
                "--prompt",
                "smoke",
            ],
        ),
        (
            "policy get",
            [
                py,
                "-S",
                "-m",
                "octop.contrib.workbuddy.security.policy_cli",
                "--path",
                "artifacts/security/policy.json",
                "get",
            ],
        ),
        (
            "inspiration list",
            [py, "-S", "-m", "octop.contrib.workbuddy.parity_cli", "inspiration", "list"],
        ),
        (
            "bridge dry",
            [
                py,
                "-S",
                "-m",
                "octop.contrib.workbuddy.parity_cli",
                "bridge",
                "--tasks-root",
                "artifacts/tasks_verify_v9",
                "--allow",
                "--text",
                "/task verify-bridge",
            ],
        ),
        (
            "harbor score dry",
            [py, "-S", "-m", "octop.contrib.workbuddy.harbor_cli", "score", "--dry-run"],
        ),
        (
            "harbor harness",
            [py, "-S", "-m", "octop.contrib.workbuddy.harbor_cli", "harness"],
        ),
    ]
    # idempotent task create
    demo = ROOT / "artifacts" / "tasks_verify_v9" / "verify-v9-smoke"
    if demo.exists():
        import shutil

        shutil.rmtree(demo)
    failed = 0
    for label, cmd in steps:
        code = run(label, cmd)
        if code != 0:
            failed += 1
            print(f"✗ FAIL {label} (exit {code})")
        else:
            print(f"✓ OK {label}")
    print("\n" + "=" * 60)
    if failed:
        print(f"VERIFY V9 FAILED — {failed} step(s)")
        return 1
    print("VERIFY V9 OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
