# SPDX-License-Identifier: MIT
"""Tenant registry — JSON store under artifacts/tenants/_registry.json."""

from __future__ import annotations

import json
import re
import secrets
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .models import TenantContext, TenantQuota, TenantRecord, TenantUser

_SAFE_ID = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_-]{1,63}$")


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def hash_api_key(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def validate_id(value: str, *, label: str = "id") -> str:
    value = (value or "").strip()
    if not _SAFE_ID.match(value):
        raise ValueError(f"invalid {label}: {value!r} (use [a-zA-Z0-9_-], 2–64 chars)")
    return value


class TenantRegistry:
    """Process-local registry with file persistence."""

    def __init__(self, path: Path | str | None = None) -> None:
        self.path = Path(path or "artifacts/tenants/_registry.json")

    def _load(self) -> dict[str, Any]:
        if not self.path.is_file():
            return {"version": 1, "tenants": {}}
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {"version": 1, "tenants": {}}
        if not isinstance(data, dict):
            return {"version": 1, "tenants": {}}
        tenants = data.get("tenants")
        if not isinstance(tenants, dict):
            data["tenants"] = {}
        return data

    def _save(self, data: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        tmp.replace(self.path)

    def list_tenants(self) -> list[TenantRecord]:
        data = self._load()
        out: list[TenantRecord] = []
        for raw in (data.get("tenants") or {}).values():
            if isinstance(raw, dict):
                out.append(TenantRecord.from_dict(raw))
        return sorted(out, key=lambda t: t.tenant_id)

    def get(self, tenant_id: str) -> TenantRecord | None:
        data = self._load()
        raw = (data.get("tenants") or {}).get(tenant_id)
        if not isinstance(raw, dict):
            return None
        return TenantRecord.from_dict(raw)

    def create(
        self,
        tenant_id: str,
        *,
        name: str = "",
        admin_user_id: str = "admin",
        quota: TenantQuota | None = None,
    ) -> tuple[TenantRecord, str]:
        """Create tenant + admin user. Returns (record, admin_api_key_plaintext)."""
        tid = validate_id(tenant_id, label="tenant_id")
        uid = validate_id(admin_user_id, label="user_id")
        if self.get(tid) is not None:
            raise ValueError(f"tenant already exists: {tid}")
        api_key = secrets.token_urlsafe(24)
        admin = TenantUser(
            user_id=uid,
            display_name="Admin",
            role="admin",
            api_key_hash=hash_api_key(api_key),
        )
        rec = TenantRecord(
            tenant_id=tid,
            name=(name or tid).strip(),
            created_at=_utc_now(),
            quota=quota or TenantQuota(),
            users=[admin],
        )
        data = self._load()
        data.setdefault("tenants", {})[tid] = rec.to_dict()
        self._save(data)
        # Ensure directory skeleton
        from .roots import TenantRoots

        TenantRoots(tid, uid).ensure()
        return rec, api_key

    def add_user(
        self,
        tenant_id: str,
        user_id: str,
        *,
        role: str = "user",
        display_name: str = "",
    ) -> tuple[TenantUser, str]:
        tid = validate_id(tenant_id, label="tenant_id")
        uid = validate_id(user_id, label="user_id")
        rec = self.get(tid)
        if rec is None:
            raise ValueError(f"tenant not found: {tid}")
        if any(u.user_id == uid for u in rec.users):
            raise ValueError(f"user already exists: {uid}")
        if len(rec.users) >= rec.quota.max_users:
            raise ValueError(f"user quota exceeded ({rec.quota.max_users})")
        api_key = secrets.token_urlsafe(24)
        user = TenantUser(
            user_id=uid,
            display_name=display_name or uid,
            role=role if role in {"admin", "user", "auditor"} else "user",
            api_key_hash=hash_api_key(api_key),
        )
        rec.users.append(user)
        data = self._load()
        data["tenants"][tid] = rec.to_dict()
        self._save(data)
        from .roots import TenantRoots

        TenantRoots(tid, uid).ensure()
        return user, api_key

    def authenticate(self, tenant_id: str, user_id: str, api_key: str) -> TenantContext:
        rec = self.get(tenant_id)
        if rec is None or rec.disabled:
            raise ValueError("invalid credentials")
        user = next((u for u in rec.users if u.user_id == user_id), None)
        if user is None or user.disabled:
            raise ValueError("invalid credentials")
        if not user.api_key_hash or not hmac_compare(user.api_key_hash, hash_api_key(api_key)):
            raise ValueError("invalid credentials")
        return TenantContext(tenant_id=rec.tenant_id, user_id=user.user_id, role=user.role)

    def set_quota(self, tenant_id: str, quota: TenantQuota) -> TenantRecord:
        rec = self.get(tenant_id)
        if rec is None:
            raise ValueError(f"tenant not found: {tenant_id}")
        rec.quota = quota
        data = self._load()
        data["tenants"][tenant_id] = rec.to_dict()
        self._save(data)
        return rec

    def disable(self, tenant_id: str, *, disabled: bool = True) -> TenantRecord:
        rec = self.get(tenant_id)
        if rec is None:
            raise ValueError(f"tenant not found: {tenant_id}")
        rec.disabled = disabled
        data = self._load()
        data["tenants"][tenant_id] = rec.to_dict()
        self._save(data)
        return rec


def hmac_compare(a: str, b: str) -> bool:
    import hmac

    return hmac.compare_digest(a.encode("utf-8"), b.encode("utf-8"))
