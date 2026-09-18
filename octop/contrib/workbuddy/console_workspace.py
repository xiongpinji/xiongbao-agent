# SPDX-License-Identifier: MIT
"""Workspace views for a task directory — artifacts / files / changes / preview."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_TEXT_EXT = {
    ".txt",
    ".md",
    ".json",
    ".py",
    ".ts",
    ".tsx",
    ".js",
    ".jsx",
    ".html",
    ".css",
    ".yml",
    ".yaml",
    ".toml",
    ".csv",
    ".xml",
    ".svg",
}
_PREVIEW_MAX = 80_000


def _rel(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.name


def list_files(task_dir: Path, *, limit: int = 200) -> list[dict[str, Any]]:
    root = Path(task_dir)
    if not root.is_dir():
        return []
    rows: list[dict[str, Any]] = []
    for p in sorted(root.rglob("*")):
        if not p.is_file():
            continue
        if p.name.startswith("."):
            continue
        st = p.stat()
        rows.append(
            {
                "path": _rel(p, root),
                "bytes": st.st_size,
                "ext": p.suffix.lower(),
            }
        )
        if len(rows) >= limit:
            break
    return rows


def workspace_payload(task_dir: Path, record: dict[str, Any] | None = None) -> dict[str, Any]:
    """Build four-tab Results panel payload."""
    root = Path(task_dir)
    files = list_files(root)
    results = list((record or {}).get("results") or [])
    artifacts = [
        f
        for f in files
        if f["path"] != "task.json"
        and not f["path"].startswith("messages")
        and f["ext"] in {".md", ".html", ".csv", ".json", ".xlsx", ".docx", ".pptx", ".pdf", ".png", ".svg"}
    ]
    # Prefer explicit result entries marked as artifacts
    for r in results:
        if isinstance(r, dict) and r.get("kind") in {"artifact", "summary", "dry_run_plan"}:
            artifacts.append(
                {
                    "path": f"result:{r.get('kind')}",
                    "bytes": len(json.dumps(r, ensure_ascii=False)),
                    "ext": ".json",
                    "payload": r,
                }
            )

    changes: list[dict[str, Any]] = []
    for r in results:
        if not isinstance(r, dict):
            continue
        if r.get("kind") in {"goal_run", "dry_run_plan", "diff", "change"}:
            changes.append(r)
    # Files other than task.json count as workspace changes snapshot
    for f in files:
        if f["path"] != "task.json":
            changes.append({"kind": "file", "path": f["path"], "bytes": f["bytes"]})

    preview: dict[str, Any] = {"ok": False, "path": "", "content": "", "content_type": "text/plain"}
    candidates = [f for f in files if f["ext"] in _TEXT_EXT and f["path"] != "task.json"]
    if not candidates:
        candidates = [f for f in files if f["path"] == "task.json"]
    if candidates:
        pick = candidates[0]
        path = root / pick["path"]
        try:
            raw = path.read_text(encoding="utf-8", errors="replace")
            if len(raw) > _PREVIEW_MAX:
                raw = raw[:_PREVIEW_MAX] + "\n…(truncated)"
            preview = {
                "ok": True,
                "path": pick["path"],
                "content": raw,
                "content_type": "text/html" if pick["ext"] == ".html" else "text/plain",
            }
        except OSError as exc:
            preview = {"ok": False, "path": pick["path"], "content": str(exc), "content_type": "text/plain"}

    return {
        "ok": True,
        "artifacts": artifacts[:80],
        "files": files,
        "changes": changes[:120],
        "preview": preview,
    }


def read_preview(task_dir: Path, rel_path: str) -> dict[str, Any]:
    root = Path(task_dir).resolve()
    target = (root / rel_path).resolve()
    if not str(target).startswith(str(root)) or not target.is_file():
        return {"ok": False, "error": "file not found"}
    try:
        raw = target.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        return {"ok": False, "error": str(exc)}
    if len(raw) > _PREVIEW_MAX:
        raw = raw[:_PREVIEW_MAX] + "\n…(truncated)"
    return {
        "ok": True,
        "path": rel_path,
        "content": raw,
        "content_type": "text/html" if target.suffix.lower() == ".html" else "text/plain",
    }
