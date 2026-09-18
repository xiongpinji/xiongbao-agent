# SPDX-License-Identifier: MIT
"""Update hub with V11 multi-tenant surfaces."""

from __future__ import annotations

import json
import os
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
    tenants_reg = root / "artifacts" / "tenants" / "_registry.json"
    tenant_count = 0
    if tenants_reg.is_file():
        try:
            data = json.loads(tenants_reg.read_text(encoding="utf-8"))
            tenant_count = len(data.get("tenants") or {})
        except (OSError, json.JSONDecodeError):
            tenant_count = -1
    return {
        "ok": True,
        "v": 17,
        "root": str(root),
        "harbor": harbor.to_dict(),
        "harness": harness_mount_probe(root=root),
        "enterprise": enterprise,
        "audit": {"path": str(audit_path), "lines": audit_lines},
        "tasks": {"root": str(tasks_root), "count": task_count},
        "tenants": {
            "registry": str(tenants_reg),
            "count": tenant_count,
            "multi_tenant": (os.environ.get("WB_MULTI_TENANT") or "").strip() in {"1", "true", "yes"},
            "console_auth": (os.environ.get("WB_CONSOLE_AUTH") or os.environ.get("WB_MULTI_TENANT") or "").strip()
            in {"1", "true", "yes"},
            "cli": "python -S -m octop.contrib.workbuddy.tenant_cli",
        },
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
            "hint": "docker compose -f deploy/docker-compose.workbuddy.yml --profile prod up -d",
            "profiles": ["full", "casdoor", "milvus", "prod"],
        },
        "console": {
            "default_port": 8010,
            "path": "/",
            "ops": "/ops.html",
            "apis": [
                "/api/health",
                "/api/auth/login",
                "/api/status",
                "/api/tasks",
                "/api/tasks/{id}",
                "/api/tasks/{id}/workspace",
                "/api/tasks/{id}/messages",
                "/api/tasks/{id}/upload",
                "/api/tasks/{id}/download",
                "/api/tasks/{id}/delete",
                "/api/tasks/{id}/patch",
                "/api/skills",
                "/api/skills/install",
                "/api/enterprise",
                "/api/harbor",
                "/api/harbor/dry-run",
                "/api/harbor/score",
                "/api/connectors",
                "/api/runtime",
                "/api/tenant",
            ],
        },
    }


def hub_status_json(**kwargs: Any) -> str:
    return json.dumps(hub_status(**kwargs), ensure_ascii=False, indent=2)
