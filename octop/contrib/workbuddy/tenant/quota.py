# SPDX-License-Identifier: MIT
"""Tenant quota enforcement."""

from __future__ import annotations

from pathlib import Path

from .models import TenantQuota, TenantRecord
from .roots import TenantRoots


class QuotaExceeded(Exception):
    def __init__(self, message: str, *, code: str = "quota_exceeded") -> None:
        super().__init__(message)
        self.code = code


def _dir_size_bytes(path: Path) -> int:
    if not path.exists():
        return 0
    total = 0
    for p in path.rglob("*"):
        if p.is_file():
            try:
                total += p.stat().st_size
            except OSError:
                continue
    return total


def count_tasks(roots: TenantRoots) -> int:
    if not roots.tasks.is_dir():
        return 0
    return sum(1 for p in roots.tasks.iterdir() if (p / "task.json").is_file())


def storage_mb(roots: TenantRoots) -> float:
    return _dir_size_bytes(roots.root) / (1024 * 1024)


def check_can_create_task(rec: TenantRecord, roots: TenantRoots) -> None:
    q: TenantQuota = rec.quota
    n = count_tasks(roots)
    if n >= q.max_tasks:
        raise QuotaExceeded(f"task quota exceeded: {n}/{q.max_tasks}", code="max_tasks")
    used = storage_mb(roots)
    if used >= q.max_storage_mb:
        raise QuotaExceeded(
            f"storage quota exceeded: {used:.1f}/{q.max_storage_mb} MB",
            code="max_storage_mb",
        )


def usage_snapshot(rec: TenantRecord, user_id: str) -> dict:
    roots = TenantRoots(rec.tenant_id, user_id)
    return {
        "tenant_id": rec.tenant_id,
        "user_id": user_id,
        "tasks": count_tasks(roots),
        "storage_mb": round(storage_mb(roots), 2),
        "users": len(rec.users),
        "quota": rec.quota.to_dict(),
    }
