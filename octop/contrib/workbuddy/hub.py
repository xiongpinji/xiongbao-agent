# SPDX-License-Identifier: MIT
"""Update hub with V10 runtime surfaces."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .bench.harbor import harbor_status, harness_mount_probe, project_root
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
    tasks_root = root / "artifacts" / "tasks"
    task_count = 0
    if tasks_root.is_dir():
        task_count = sum(1 for p in tasks_root.iterdir() if (p / "task.json").is_file())
    installed = root / "artifacts" / "skillhub" / "installed"
    installed_count = 0
    if installed.is_dir():
        installed_count = sum(1 for p in installed.iterdir() if p.is_dir() and (p / "SKILL.md").is_file())
    return {
        "ok": True,
        "v": 10,
        "root": str(root),
        "harbor": harbor.to_dict(),
        "harness": harness_mount_probe(root=root),
        "enterprise": enterprise,
        "audit": {"path": str(audit_path), "lines": audit_lines},
        "tasks": {"root": str(tasks_root), "count": task_count},
        "runtime": {
            "cli": "python -S -m octop.contrib.workbuddy.runtime_cli",
            "commands": [
                "run-task",
                "policy-check",
                "profile-apply",
                "inbox-poll",
                "skill-register",
                "kb-prefix",
                "bundle-export",
                "task-worktree",
                "cowrite-publish",
            ],
            "installed_skills": installed_count,
        },
        "compose": {
            "file": str(root / "deploy" / "docker-compose.workbuddy.yml"),
            "hint": "docker compose -f deploy/docker-compose.workbuddy.yml up -d",
            "profiles": ["full", "casdoor", "milvus"],
        },
        "console": {
            "default_port": 8010,
            "path": "/",
            "apis": [
                "/api/status",
                "/api/tasks",
                "/api/skills",
                "/api/connectors",
                "/api/harbor",
                "/api/runtime",
            ],
        },
    }


def hub_status_json(**kwargs: Any) -> str:
    return json.dumps(hub_status(**kwargs), ensure_ascii=False, indent=2)
