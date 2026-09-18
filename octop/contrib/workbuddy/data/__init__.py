# SPDX-License-Identifier: MIT
"""Workspace data export / import (zip + manifest)."""

from __future__ import annotations

import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def export_workspace(
    source: Path | str,
    archive: Path | str,
    *,
    include_globs: list[str] | None = None,
) -> dict[str, Any]:
    """Zip a workspace directory with a manifest.json."""
    src = Path(source)
    out = Path(archive)
    out.parent.mkdir(parents=True, exist_ok=True)
    if not src.is_dir():
        raise FileNotFoundError(f"source not found: {src}")
    files: list[str] = []
    patterns = include_globs or ["**/*"]
    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for pattern in patterns:
            for path in sorted(src.glob(pattern)):
                if not path.is_file():
                    continue
                rel = path.relative_to(src).as_posix()
                if rel == "manifest.json":
                    continue
                zf.write(path, arcname=rel)
                files.append(rel)
        manifest = {
            "exported_at": _utc(),
            "source": str(src.resolve()),
            "file_count": len(files),
            "files": files,
        }
        zf.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
    return {"archive": str(out), "file_count": len(files), "manifest": manifest}


def import_workspace(
    archive: Path | str,
    dest: Path | str,
    *,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Extract archive into dest; refuses non-empty dest unless overwrite."""
    arc = Path(archive)
    target = Path(dest)
    if not arc.is_file():
        raise FileNotFoundError(f"archive not found: {arc}")
    if target.exists() and any(target.iterdir()) and not overwrite:
        raise FileExistsError(f"dest not empty: {target}")
    target.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(arc, "r") as zf:
        # path traversal guard
        for info in zf.infolist():
            name = info.filename.replace("\\", "/")
            if name.startswith("/") or ".." in name.split("/"):
                raise ValueError(f"unsafe path in archive: {info.filename}")
        zf.extractall(target)
        names = [i.filename for i in zf.infolist() if not i.is_dir()]
    manifest_path = target / "manifest.json"
    manifest: dict[str, Any] = {}
    if manifest_path.is_file():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    return {
        "dest": str(target),
        "file_count": len(names),
        "manifest": manifest,
    }
