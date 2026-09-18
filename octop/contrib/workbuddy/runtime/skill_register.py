# SPDX-License-Identifier: MIT
"""Install skill and register into local installed index for Catalog."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..skills.catalog import SkillCatalog
from ..skills.market import install_from_vendor, install_skill, scan_skill_dir


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _index_path(dest_root: Path) -> Path:
    return dest_root / "installed.json"


def register_installed_skill(
    source: Path | str | None = None,
    *,
    skill_id: str | None = None,
    dest_root: Path | str = "artifacts/skillhub/installed",
    vendor_skills: Path | str | None = None,
    force: bool = False,
    require_scan_ok: bool = False,
) -> dict[str, Any]:
    """Install then append to ``installed.json`` and verify Catalog sees it."""
    dest_root = Path(dest_root)
    dest_root.mkdir(parents=True, exist_ok=True)
    if skill_id:
        result = install_from_vendor(
            skill_id,
            dest_root,
            vendor_skills=vendor_skills,
            force=force,
        )
    elif source:
        result = install_skill(
            source,
            dest_root,
            force=force,
            require_scan_ok=require_scan_ok,
        )
    else:
        raise ValueError("provide source or skill_id")

    if not result.get("installed"):
        return {**result, "registered": False}

    dest = Path(str(result["dest"]))
    scan = scan_skill_dir(dest)
    idx_path = _index_path(dest_root)
    rows: list[dict[str, Any]] = []
    if idx_path.is_file():
        try:
            data = json.loads(idx_path.read_text(encoding="utf-8"))
            if isinstance(data, list):
                rows = data
        except json.JSONDecodeError:
            rows = []
    entry = {
        "id": dest.name,
        "path": str(dest),
        "installed_at": _utc(),
        "scan_ok": scan.ok,
        "findings": len(scan.findings),
    }
    rows = [r for r in rows if r.get("id") != dest.name]
    rows.append(entry)
    idx_path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")

    cat = SkillCatalog(skills_root=dest_root, include_builtin=False)
    n = cat.scan(force=True)
    visible = dest.name in {m.id for m in cat.list()}
    return {
        **result,
        "registered": True,
        "index": str(idx_path),
        "catalog_count": n,
        "visible_in_catalog": visible,
        "scan": scan.to_dict(),
    }
