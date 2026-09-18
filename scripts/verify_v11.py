#!/usr/bin/env python
# SPDX-License-Identifier: MIT
"""Verify V11 multi-tenant production wiring.

Usage::

    python -S scripts/verify_v11.py
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
        ("v11 unit tests", [py, "-S", "tests/contrib/workbuddy/test_v11_tenant.py"]),
        ("hub status v11", [py, "-S", "-m", "octop.contrib.workbuddy.hub_cli", "status"]),
        (
            "tenant create+login+roots",
            [
                py,
                "-S",
                "-c",
                (
                    "import json,tempfile,os;"
                    "from pathlib import Path;"
                    "from octop.contrib.workbuddy.tenant import TenantRegistry,TenantRoots,issue_token,verify_token,tenant_collection;"
                    "td=tempfile.mkdtemp();"
                    "os.environ['WB_ARTIFACTS_ROOT']=td;"
                    "os.environ['WB_CONSOLE_SECRET']='verify-v11-secret';"
                    "reg=TenantRegistry(Path(td)/'_registry.json');"
                    "rec,key=reg.create('verifyco',name='Verify');"
                    "ctx=reg.authenticate('verifyco','admin',key);"
                    "tok=issue_token(ctx);"
                    "assert verify_token(tok).tenant_id=='verifyco';"
                    "roots=TenantRoots('verifyco','admin');"
                    "roots.ensure();"
                    "assert roots.tasks.is_dir();"
                    "assert tenant_collection('verifyco')=='wb_verifyco';"
                    "print('TENANT OK', json.dumps(roots.to_dict()));"
                ),
            ],
        ),
        (
            "docs present",
            [
                py,
                "-S",
                "-c",
                (
                    "from pathlib import Path;"
                    "assert Path('deploy/enterprise/MULTI_TENANT.md').is_file();"
                    "assert Path('deploy/caddy/Caddyfile').is_file();"
                    "print('DOCS OK');"
                ),
            ],
        ),
    ]
    failed = 0
    for label, cmd in steps:
        code = run(label, cmd)
        if code != 0:
            failed += 1
            print(f"FAIL {label} exit={code}")
        else:
            print(f"OK {label}")
    if failed:
        print(f"\nVERIFY V11 FAILED ({failed})")
        return 1
    print("\nVERIFY V11 OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
