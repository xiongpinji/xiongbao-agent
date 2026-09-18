# SPDX-License-Identifier: MIT
"""Per-tenant filesystem roots — isolation contract for multi-tenant deploy."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def artifacts_base() -> Path:
    """Global artifacts root (override with WB_ARTIFACTS_ROOT)."""
    raw = (os.environ.get("WB_ARTIFACTS_ROOT") or "").strip()
    if raw:
        return Path(raw)
    return Path("artifacts")


@dataclass(frozen=True)
class TenantRoots:
    """Resolved paths for one (tenant_id, user_id) pair.

    Layout::

        artifacts/tenants/<tid>/users/<uid>/
            tasks/
            knowledge/
            cowrite/
            library/
            security/
            models/
            china_im/
            skillhub/
        artifacts/tenants/<tid>/_shared/   # optional tenant-wide shared
    """

    tenant_id: str
    user_id: str
    base: Path | None = None

    @property
    def root(self) -> Path:
        base = self.base or artifacts_base()
        return base / "tenants" / self.tenant_id / "users" / self.user_id

    @property
    def tenant_root(self) -> Path:
        base = self.base or artifacts_base()
        return base / "tenants" / self.tenant_id

    @property
    def shared(self) -> Path:
        return self.tenant_root / "_shared"

    @property
    def tasks(self) -> Path:
        return self.root / "tasks"

    @property
    def knowledge(self) -> Path:
        return self.root / "knowledge"

    @property
    def cowrite(self) -> Path:
        return self.root / "cowrite"

    @property
    def library(self) -> Path:
        return self.root / "library"

    @property
    def security(self) -> Path:
        return self.root / "security"

    @property
    def models(self) -> Path:
        return self.root / "models"

    @property
    def china_im(self) -> Path:
        return self.root / "china_im"

    @property
    def skillhub(self) -> Path:
        return self.root / "skillhub"

    def ensure(self) -> None:
        for p in (
            self.tasks,
            self.knowledge,
            self.cowrite,
            self.library,
            self.security,
            self.models,
            self.china_im,
            self.skillhub / "installed",
            self.shared,
        ):
            p.mkdir(parents=True, exist_ok=True)

    def to_dict(self) -> dict[str, str]:
        return {
            "tenant_id": self.tenant_id,
            "user_id": self.user_id,
            "root": str(self.root),
            "tasks": str(self.tasks),
            "knowledge": str(self.knowledge),
            "cowrite": str(self.cowrite),
            "library": str(self.library),
            "security": str(self.security),
            "models": str(self.models),
            "china_im": str(self.china_im),
            "skillhub": str(self.skillhub),
            "shared": str(self.shared),
        }


def resolve_from_env() -> TenantRoots | None:
    """If WB_TENANT_ID + WB_USER_ID set, return roots; else None (legacy single-root)."""
    tid = (os.environ.get("WB_TENANT_ID") or "").strip()
    uid = (os.environ.get("WB_USER_ID") or "").strip()
    if not tid or not uid:
        return None
    return TenantRoots(tid, uid)


def legacy_ok() -> bool:
    """Allow legacy artifacts/* when multi-tenant not forced."""
    return (os.environ.get("WB_MULTI_TENANT") or "").strip() not in {"1", "true", "yes"}
