#!/usr/bin/env python
# SPDX-License-Identifier: MIT
"""V5 deliverable verification: office llm-lite + deploy packaging files.

Usage::

    python -S scripts/verify_v5.py
    python -S scripts/verify_v5.py --live   # optional: call local Ollama on 1–3 tasks
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
    parser = argparse.ArgumentParser(description="V5 verify")
    parser.add_argument(
        "--live",
        action="store_true",
        help="Also run 2 office tasks against local LLM (needs Ollama)",
    )
    parser.add_argument("--limit", type=int, default=2, help="Live office task limit")
    parser.add_argument(
        "--pass-rate",
        type=float,
        default=0.0,
        help="Live gate (default 0 = report only)",
    )
    args = parser.parse_args(argv)
    py = sys.executable

    steps: list[tuple[str, list[str]]] = [
        ("bench smoke unit", [py, "-S", "tests/contrib/workbuddy/test_bench.py"]),
        ("office llm_judge unit", [py, "-S", "tests/contrib/workbuddy/test_llm_judge.py"]),
        (
            "list office dataset",
            [
                py,
                "-S",
                "-m",
                "octop.contrib.workbuddy.bench.cli",
                "--office",
                "--list-office",
                "--dry-sample-only",
                "--out-dir",
                "artifacts/bench_v5",
            ],
        ),
    ]

    failed: list[str] = []
    for label, cmd in steps:
        code = run(label, cmd)
        if code != 0:
            failed.append(label)
            print(f"✗ {label} exit={code}")
        else:
            print(f"✓ {label}")

    # Packaging files must exist
    required = [
        ROOT / "deploy" / "systemd" / "octop.service",
        ROOT / "deploy" / "systemd" / "octop-tick.service",
        ROOT / "deploy" / "systemd" / "octop-tick.timer",
        ROOT / "deploy" / "enterprise" / "README.md",
        ROOT / "scripts" / "fetch_office_dataset.ps1",
    ]
    print("\n" + "=" * 60)
    print("▶ packaging files")
    print("=" * 60)
    for path in required:
        if path.is_file():
            print(f"✓ {path.relative_to(ROOT)}")
        else:
            print(f"✗ missing {path.relative_to(ROOT)}")
            failed.append(str(path.relative_to(ROOT)))

    if args.live:
        live_cmd = [
            py,
            "-S",
            "-m",
            "octop.contrib.workbuddy.bench.cli",
            "--office",
            "--live-llm",
            "--no-judge",
            "--limit",
            str(max(1, args.limit)),
            "--pass-rate",
            str(args.pass_rate),
            "--out-dir",
            "artifacts/bench_v5_live",
        ]
        code = run("office live llm_lite", live_cmd)
        if code != 0:
            failed.append("office live llm_lite")
            print(f"✗ office live exit={code}")
        else:
            print("✓ office live llm_lite")

    print("\n" + "=" * 60)
    if failed:
        print(f"V5 VERIFY FAILED: {len(failed)} step(s): {', '.join(failed)}")
        return 1
    print("V5 VERIFY OK — office llm-lite + enterprise packaging docs ready")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
