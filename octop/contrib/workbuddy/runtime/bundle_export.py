# SPDX-License-Identifier: MIT
"""Multi-root parity bundle export / import."""

from __future__ import annotations

import json
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..data import export_workspace, import_workspace

DEFAULT_ROOTS = (
    "tasks",
    "knowledge",
    "cowrite",
    "library",
    "security",
    "models",
    "china_im",
)


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def export_parity_bundle(
    artifacts_root: Path | str,
    archive: Path | str,
    *,
    roots: list[str] | None = None,
) -> dict[str, Any]:
    """Zip selected subdirs under artifacts/ into one archive."""
    base = Path(artifacts_root)
    out = Path(archive)
    out.parent.mkdir(parents=True, exist_ok=True)
    names = list(roots or DEFAULT_ROOTS)
    with tempfile.TemporaryDirectory() as tmp:
        staging = Path(tmp) / "bundle"
        staging.mkdir()
        included: list[str] = []
        for name in names:
            src = base / name
            if not src.is_dir():
                continue
            dest = staging / name
            shutil.copytree(src, dest)
            included.append(name)
        meta = {
            "kind": "workbuddy-parity-bundle",
            "exported_at": _utc(),
            "roots": included,
            "source": str(base.resolve()),
        }
        (staging / "bundle.json").write_text(
            json.dumps(meta, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        result = export_workspace(staging, out)
        result["roots"] = included
        result["bundle"] = meta
        return result


def import_parity_bundle(
    archive: Path | str,
    artifacts_root: Path | str,
    *,
    overwrite: bool = True,
) -> dict[str, Any]:
    """Extract bundle into artifacts_root (merges subdirs)."""
    base = Path(artifacts_root)
    base.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        dest = Path(tmp) / "extracted"
        info = import_workspace(archive, dest, overwrite=True)
        bundle_meta: dict[str, Any] = {}
        bp = dest / "bundle.json"
        if bp.is_file():
            bundle_meta = json.loads(bp.read_text(encoding="utf-8"))
        restored: list[str] = []
        for child in sorted(dest.iterdir()):
            if not child.is_dir():
                continue
            target = base / child.name
            if target.exists():
                if not overwrite:
                    continue
                shutil.rmtree(target)
            shutil.copytree(child, target)
            restored.append(child.name)
        return {
            "dest": str(base),
            "restored": restored,
            "bundle": bundle_meta,
            "file_count": info.get("file_count", 0),
        }
