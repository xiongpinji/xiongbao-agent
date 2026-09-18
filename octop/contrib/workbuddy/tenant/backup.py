# SPDX-License-Identifier: MIT
"""Per-tenant backup / restore (filesystem slice)."""

from __future__ import annotations

import json
import shutil
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .registry import TenantRegistry
from .roots import artifacts_base


def _utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def backup_tenant(
    tenant_id: str,
    out: Path | str,
    *,
    registry: TenantRegistry | None = None,
    base: Path | None = None,
) -> dict[str, Any]:
    """Zip ``artifacts/tenants/<tid>/`` plus registry entry."""
    reg = registry or TenantRegistry()
    rec = reg.get(tenant_id)
    if rec is None:
        raise ValueError(f"tenant not found: {tenant_id}")
    base = base or artifacts_base()
    src = base / "tenants" / tenant_id
    if not src.is_dir():
        raise ValueError(f"tenant data missing: {src}")
    out_path = Path(out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    manifest = {
        "kind": "wb-tenant-backup",
        "version": 1,
        "tenant_id": tenant_id,
        "created_at": _utc_stamp(),
        "record": rec.to_dict(),
    }
    with zipfile.ZipFile(out_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
        for path in src.rglob("*"):
            if path.is_file():
                arc = Path("data") / path.relative_to(src)
                zf.write(path, arcname=str(arc).replace("\\", "/"))
    return {
        "ok": True,
        "tenant_id": tenant_id,
        "archive": str(out_path),
        "bytes": out_path.stat().st_size,
    }


def restore_tenant(
    archive: Path | str,
    *,
    registry: TenantRegistry | None = None,
    base: Path | None = None,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Restore a tenant slice; refuses to clobber unless overwrite=True."""
    reg = registry or TenantRegistry()
    base = base or artifacts_base()
    archive_path = Path(archive)
    with zipfile.ZipFile(archive_path, "r") as zf:
        raw = zf.read("manifest.json")
        manifest = json.loads(raw.decode("utf-8"))
        tid = str(manifest.get("tenant_id") or "")
        if not tid:
            raise ValueError("manifest missing tenant_id")
        dest = base / "tenants" / tid
        if dest.exists() and not overwrite:
            raise ValueError(f"tenant data exists (use overwrite): {dest}")
        if dest.exists() and overwrite:
            shutil.rmtree(dest)
        dest.mkdir(parents=True, exist_ok=True)
        for info in zf.infolist():
            name = info.filename
            if not name.startswith("data/") or info.is_dir():
                continue
            rel = name[len("data/") :]
            if not rel or ".." in rel.split("/"):
                continue
            target = dest / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(info) as src, target.open("wb") as dst:
                shutil.copyfileobj(src, dst)
        record = manifest.get("record")
        if isinstance(record, dict):
            data = reg._load()  # noqa: SLF001 — intentional restore into registry
            data.setdefault("tenants", {})[tid] = record
            reg._save(data)  # noqa: SLF001
    return {"ok": True, "tenant_id": tid, "dest": str(base / "tenants" / tid)}
