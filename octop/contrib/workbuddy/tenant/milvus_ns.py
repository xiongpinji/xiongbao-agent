# SPDX-License-Identifier: MIT
"""Milvus collection naming scoped by tenant."""

from __future__ import annotations

import re

_SAFE = re.compile(r"[^a-zA-Z0-9_]+")


def tenant_collection(tenant_id: str, *, base: str = "wb") -> str:
    """Return ``wb_<tid>`` sanitized for Milvus collection names."""
    tid = _SAFE.sub("_", (tenant_id or "").strip()).strip("_").lower()
    if not tid:
        tid = "default"
    if tid[0].isdigit():
        tid = "t_" + tid
    return f"{base}_{tid}"[:255]
