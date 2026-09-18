# SPDX-License-Identifier: MIT
"""Delivery pack gate — playbook + isolation/quota + docs present."""

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
    return int(subprocess.run(argv, cwd=str(ROOT), env=env).returncode)


def main() -> int:
    py = sys.executable
    steps = [
        ("customer playbook", [py, "-S", "scripts/verify_customer_playbook.py"]),
        ("parity gaps", [py, "-S", "scripts/verify_parity_gaps.py"]),
        ("v20 parity", [py, "-S", "scripts/verify_v20.py"]),
        (
            "acceptance docs",
            [
                py,
                "-S",
                "-c",
                (
                    "from pathlib import Path;"
                    "files=["
                    "'deploy/enterprise/ACCEPTANCE_PACK.md',"
                    "'deploy/enterprise/GO_LIVE_CHECKLIST.md',"
                    "'deploy/enterprise/CUSTOMER_ONBOARD.md',"
                    "'deploy/enterprise/RELIABILITY.md',"
                    "'deploy/enterprise/CHANNEL_INBOUND.md',"
                    "];"
                    "[Path(f).resolve().read_text(encoding='utf-8') for f in files];"
                    "print('DOCS OK', len(files));"
                ),
            ],
        ),
    ]
    failed = 0
    for label, cmd in steps:
        if run(label, cmd) != 0:
            failed += 1
    if failed:
        print(f"\nVERIFY DELIVERY PACK FAIL ({failed})")
        return 1
    print("\nVERIFY DELIVERY PACK OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
