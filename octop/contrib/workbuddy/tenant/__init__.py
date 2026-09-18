# SPDX-License-Identifier: MIT
"""WorkBuddy multi-tenant package — production isolation layer."""

from __future__ import annotations

from .auth import (
    auth_required,
    exchange_casdoor_token,
    issue_token,
    parse_bearer,
    verify_token,
)
from .backup import backup_tenant, restore_tenant
from .milvus_ns import tenant_collection
from .models import TenantContext, TenantQuota, TenantRecord, TenantUser
from .quota import QuotaExceeded, check_can_create_task, usage_snapshot
from .registry import TenantRegistry
from .roots import TenantRoots, resolve_from_env

__all__ = [
    "QuotaExceeded",
    "TenantContext",
    "TenantQuota",
    "TenantRecord",
    "TenantRegistry",
    "TenantRoots",
    "TenantUser",
    "auth_required",
    "backup_tenant",
    "check_can_create_task",
    "exchange_casdoor_token",
    "issue_token",
    "parse_bearer",
    "resolve_from_env",
    "restore_tenant",
    "tenant_collection",
    "usage_snapshot",
    "verify_token",
]
