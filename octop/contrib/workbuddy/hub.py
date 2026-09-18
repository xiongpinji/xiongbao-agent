# SPDX-License-Identifier: MIT
"""WorkBuddy hub: aggregate status for CLI + Console API."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .bench.harbor import harbor_status, project_root
from .enterprise.probe import enterprise_probe


def hub_status(*, root: Path | None = None) -> dict[str, Any]:
    root = root or project_root()
    harbor = harbor_status(root)
    enterprise = enterprise_probe()
    audit_path = root / "octop" / "contrib" / "workbuddy" / ".runtime" / "audit.jsonl"
    audit_lines = 0
    if audit_path.is_file():
        try:
            with audit_path.open(encoding="utf-8") as fh:
                audit_lines = sum(1 for line in fh if line.strip())
        except OSError:
            audit_lines = -1
    return {
        "ok": True,
        "root": str(root),
        "harbor": harbor.to_dict(),
        "enterprise": enterprise,
        "audit": {"path": str(audit_path), "lines": audit_lines},
        "compose": {
            "file": str(root / "deploy" / "docker-compose.workbuddy.yml"),
            "hint": "docker compose -f deploy/docker-compose.workbuddy.yml up -d",
            "profiles": ["full", "casdoor", "milvus"],
        },
        "console": {"default_port": 8010, "path": "/"},
    }


def hub_status_json(**kwargs: Any) -> str:
    return json.dumps(hub_status(**kwargs), ensure_ascii=False, indent=2)
