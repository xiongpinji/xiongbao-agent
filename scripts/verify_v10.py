#!/usr/bin/env python
# SPDX-License-Identifier: MIT
"""Verify V10 runtime wiring.

Usage::

    python -S scripts/verify_v10.py
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
        ("v10 unit tests", [py, "-S", "tests/contrib/workbuddy/test_v10_runtime.py"]),
        ("hub status v10", [py, "-S", "-m", "octop.contrib.workbuddy.hub_cli", "status"]),
        (
            "policy-check ask",
            [
                py,
                "-S",
                "-m",
                "octop.contrib.workbuddy.runtime_cli",
                "policy-check",
                "--mode",
                "ask",
                "--policy",
                "artifacts/security/policy.json",
            ],
        ),
        (
            "task create+run dry",
            [
                py,
                "-S",
                "-c",
                (
                    "from pathlib import Path;"
                    "from octop.contrib.workbuddy.task import TaskStore;"
                    "from octop.contrib.workbuddy.security import PolicyStore, SecurityPolicy;"
                    "from octop.contrib.workbuddy.runtime import run_task;"
                    "root=Path('artifacts/tasks_verify_v10');"
                    "root.mkdir(parents=True, exist_ok=True);"
                    "PolicyStore('artifacts/security/policy.json').save(SecurityPolicy(default_mode='craft'));"
                    "store=TaskStore(root);"
                    "tid='verify-v10-run';"
                    "p=root/tid/'task.json';"
                    "p.parent.mkdir(parents=True, exist_ok=True);"
                    "import shutil;"
                    "shutil.rmtree(root/tid, ignore_errors=True);"
                    "rec=store.create('verify', task_id=tid, prompt='写 hello.txt', mode='craft');"
                    "r=run_task(rec.task_id, tasks_root=root, dry_run=True, kb_root=None);"
                    "assert r.ok and r.dry_run, r;"
                    "print('TASK RUN DRY OK', r.detail.get('plan_steps'));"
                ),
            ],
        ),
    ]
    failed = 0
    for label, cmd in steps:
        code = run(label, cmd)
        if code != 0 and label != "policy-check ask":
            # ask mode check is expected to exit 2 when write blocked
            failed += 1
            print(f"FAIL {label} exit={code}")
        elif label == "policy-check ask" and code not in {0, 2}:
            failed += 1
            print(f"FAIL {label} exit={code}")
        else:
            print(f"OK {label}")
    if failed:
        print(f"\nVERIFY V10 FAILED ({failed})")
        return 1
    print("\nVERIFY V10 OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
