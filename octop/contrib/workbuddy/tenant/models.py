# SPDX-License-Identifier: MIT
"""Multi-tenant models for WorkBuddy production deployment."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class TenantQuota:
    max_users: int = 50
    max_tasks: int = 500
    max_storage_mb: int = 1024
    max_agents: int = 20

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> TenantQuota:
        data = data or {}
        return cls(
            max_users=int(data.get("max_users", 50)),
            max_tasks=int(data.get("max_tasks", 500)),
            max_storage_mb=int(data.get("max_storage_mb", 1024)),
            max_agents=int(data.get("max_agents", 20)),
        )


@dataclass
class TenantUser:
    user_id: str
    display_name: str = ""
    role: str = "user"  # admin | user | auditor
    api_key_hash: str = ""
    disabled: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TenantUser:
        return cls(
            user_id=str(data["user_id"]),
            display_name=str(data.get("display_name") or ""),
            role=str(data.get("role") or "user"),
            api_key_hash=str(data.get("api_key_hash") or ""),
            disabled=bool(data.get("disabled")),
        )


@dataclass
class TenantRecord:
    tenant_id: str
    name: str
    created_at: str = ""
    disabled: bool = False
    quota: TenantQuota = field(default_factory=TenantQuota)
    users: list[TenantUser] = field(default_factory=list)
    meta: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "tenant_id": self.tenant_id,
            "name": self.name,
            "created_at": self.created_at,
            "disabled": self.disabled,
            "quota": self.quota.to_dict(),
            "users": [u.to_dict() for u in self.users],
            "meta": dict(self.meta),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TenantRecord:
        users = [TenantUser.from_dict(u) for u in (data.get("users") or [])]
        return cls(
            tenant_id=str(data["tenant_id"]),
            name=str(data.get("name") or data["tenant_id"]),
            created_at=str(data.get("created_at") or ""),
            disabled=bool(data.get("disabled")),
            quota=TenantQuota.from_dict(data.get("quota")),
            users=users,
            meta=dict(data.get("meta") or {}),
        )


@dataclass(frozen=True)
class TenantContext:
    """Request-scoped identity for isolation."""

    tenant_id: str
    user_id: str
    role: str = "user"

    def to_claims(self) -> dict[str, str]:
        return {"tid": self.tenant_id, "uid": self.user_id, "role": self.role}
