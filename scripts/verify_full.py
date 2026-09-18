#!/usr/bin/env python
# SPDX-License-Identifier: MIT
"""Full WorkBuddy parity verification (V1–V7).

Usage::

    python -S scripts/verify_full.py
    python -S scripts/verify_full.py --harbor-build   # optional docker build-smoke
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
    parser = argparse.ArgumentParser(description="Verify full WorkBuddy parity")
    parser.add_argument("--harbor-build", action="store_true")
    args = parser.parse_args(argv)
    py = sys.executable

    steps: list[tuple[str, list[str]]] = [
        ("verify_all (V1–V6)", [py, "-S", "scripts/verify_all.py"]),
        ("v7 unit tests", [py, "-S", "tests/contrib/workbuddy/test_v7_full_parity.py"]),
        (
            "official tpl assemble",
            [
                py,
                "-S",
                "-m",
                "octop.contrib.workbuddy.modes_cli",
                "assemble",
                "--mode",
                "ask",
                "--official-tpl",
            ],
        ),
        (
            "harbor status",
            [py, "-S", "-m", "octop.contrib.workbuddy.harbor_cli", "status"],
        ),
        (
            "harbor report office",
            [
                py,
                "-S",
                "-m",
                "octop.contrib.workbuddy.harbor_cli",
                "report",
                "--subset",
                "office",
                "--limit",
                "2",
            ],
        ),
        (
            "project space",
            [
                py,
                "-S",
                "-m",
                "octop.contrib.workbuddy.project_cli",
                "--root",
                "artifacts/projects_verify",
                "create",
                "demo-v7",
                "--name",
                "Demo",
            ],
        ),
        (
            "office bundle",
            [
                py,
                "-S",
                "-m",
                "octop.contrib.workbuddy.office_cli",
                "--out",
                "artifacts/office_verify",
            ],
        ),
        (
            "audit emit",
            [
                py,
                "-S",
                "-m",
                "octop.contrib.workbuddy.audit_cli",
                "--path",
                "artifacts/audit/verify.jsonl",
                "emit",
                "verify_full",
                "--field",
                "ok=1",
            ],
        ),
        (
            "enterprise probe wired",
            [py, "-S", "-m", "octop.contrib.workbuddy.enterprise_cli", "probe"],
        ),
        (
            "connectors probe (+email/webhook)",
            [py, "-S", "-m", "octop.contrib.workbuddy.connectors_cli", "probe"],
        ),
    ]

    if args.harbor_build:
        steps.append(
            (
                "harbor build-smoke",
                [
                    py,
                    "-S",
                    "-m",
                    "octop.contrib.workbuddy.harbor_cli",
                    "build-smoke",
                    "--subset",
                    "office",
                ],
            )
        )

    failed = 0
    for label, cmd in steps:
        # project create may fail if exists — recreate by removing first
        if "project space" in label:
            demo = ROOT / "artifacts" / "projects_verify" / "demo-v7"
            if demo.exists():
                import shutil

                shutil.rmtree(demo)
        rc = run(label, cmd)
        if rc != 0:
            failed += 1
            print(f"✗ FAIL {label} rc={rc}")
        else:
            print(f"✓ OK {label}")

    # structural checks
    print("\n" + "=" * 60)
    print("▶ structural files")
    print("=" * 60)
    required = [
        ROOT / "deploy" / "docker-compose.workbuddy.yml",
        ROOT / "scripts" / "fetch_cdn_snapshot.ps1",
        ROOT / "TASKBOARD.md",
    ]
    for path in required:
        if path.is_file():
            print(f"✓ {path.relative_to(ROOT)}")
        else:
            print(f"✗ missing {path}")
            failed += 1

    if failed:
        print(f"\nVERIFY FULL FAILED — {failed} step(s)")
        return 1
    print("\nVERIFY FULL OK — WorkBuddy V7 full-parity board green")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
