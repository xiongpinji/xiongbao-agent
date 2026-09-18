# SPDX-License-Identifier: MIT
"""Publish cowrite session export into LibraryIndex."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..cowrite import CowriteStore
from ..library import LibraryIndex


def publish_cowrite_to_library(
    session_id: str,
    *,
    cowrite_root: Path | str = "artifacts/cowrite",
    library_root: Path | str = "artifacts/library",
    title: str = "",
) -> dict[str, Any]:
    store = CowriteStore(cowrite_root)
    session = store.get(session_id)
    export_path = Path(cowrite_root) / session_id / "export.md"
    store.export_markdown(session_id, export_path)
    lib = LibraryIndex(library_root)
    entry = lib.add_file(
        export_path,
        title=title or session.title or session_id,
        tags=["cowrite", session_id],
    )
    pub = lib.publish(site_title=f"Cowrite: {session.title or session_id}")
    return {
        "ok": True,
        "entry": entry.to_dict(),
        "publish": str(pub),
        "export": str(export_path),
    }
