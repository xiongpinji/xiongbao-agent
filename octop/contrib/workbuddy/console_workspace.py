# SPDX-License-Identifier: MIT
"""Workspace views for a task directory — artifacts / files / changes / preview."""

from __future__ import annotations

import base64
import json
import re
from pathlib import Path
from typing import Any

_TEXT_EXT = {
    ".txt",
    ".md",
    ".markdown",
    ".json",
    ".py",
    ".ts",
    ".tsx",
    ".js",
    ".jsx",
    ".html",
    ".htm",
    ".css",
    ".yml",
    ".yaml",
    ".toml",
    ".csv",
    ".xml",
    ".svg",
}
_IMAGE_EXT = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"}
_PREVIEW_MAX = 80_000
_UPLOAD_MAX = 5 * 1024 * 1024


def _rel(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.name


def _safe_filename(name: str) -> str:
    base = Path(name).name
    safe = re.sub(r"[^\w.\-()+ ]+", "_", base).strip(" ._")
    return safe or "upload.bin"


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


def _preview_format(ext: str) -> str:
    if ext in {".html", ".htm"}:
        return "html"
    if ext in {".md", ".markdown"}:
        return "markdown"
    if ext in _IMAGE_EXT:
        return "image"
    if ext == ".svg":
        return "html"
    if ext == ".json":
        return "json"
    return "text"


def build_preview(path: Path, *, rel: str) -> dict[str, Any]:
    ext = path.suffix.lower()
    if ext in {".docx", ".xlsx"}:
        from .office_preview import office_preview

        prev = office_preview(path)
        prev["path"] = rel
        return prev
    fmt = _preview_format(ext)
    if fmt == "image":
        data = path.read_bytes()
        if len(data) > _UPLOAD_MAX:
            return {"ok": False, "path": rel, "error": "image too large", "format": "image"}
        mime = {
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".gif": "image/gif",
            ".webp": "image/webp",
            ".bmp": "image/bmp",
        }.get(ext, "application/octet-stream")
        b64 = base64.b64encode(data).decode("ascii")
        return {
            "ok": True,
            "path": rel,
            "format": "image",
            "content_type": mime,
            "content": f"data:{mime};base64,{b64}",
        }
    try:
        raw = path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        return {"ok": False, "path": rel, "error": str(exc), "format": fmt}
    if len(raw) > _PREVIEW_MAX:
        raw = raw[:_PREVIEW_MAX] + "\n…(truncated)"
    ctype = {
        "html": "text/html",
        "markdown": "text/markdown",
        "json": "application/json",
        "text": "text/plain",
    }.get(fmt, "text/plain")
    return {
        "ok": True,
        "path": rel,
        "format": fmt,
        "content_type": ctype,
        "content": raw,
    }


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
        and (
            f["ext"]
            in {
                ".md",
                ".html",
                ".htm",
                ".csv",
                ".json",
                ".docx",
                ".xlsx",
                ".pptx",
                ".pdf",
                ".png",
                ".jpg",
                ".jpeg",
                ".svg",
                ".gif",
                ".webp",
            }
            or f["path"].startswith("attachments/")
        )
    ]
    for r in results:
        if isinstance(r, dict) and r.get("kind") in {"artifact", "summary", "dry_run_plan", "upload"}:
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
        if r.get("kind") in {"goal_run", "dry_run_plan", "diff", "change", "upload"}:
            changes.append(r)
    for f in files:
        if f["path"] != "task.json":
            changes.append({"kind": "file", "path": f["path"], "bytes": f["bytes"]})

    preview: dict[str, Any] = {"ok": False, "path": "", "content": "", "format": "text", "content_type": "text/plain"}
    candidates = [
        f
        for f in files
        if f["ext"] in _TEXT_EXT.union(_IMAGE_EXT) and f["path"] != "task.json"
    ]
    # Prefer attachments and html/md
    candidates.sort(
        key=lambda f: (
            0 if f["path"].startswith("attachments/") else 1,
            0 if f["ext"] in {".html", ".md", ".png"} else 1,
            f["path"],
        )
    )
    if not candidates:
        candidates = [f for f in files if f["path"] == "task.json"]
    if candidates:
        pick = candidates[0]
        preview = build_preview(root / pick["path"], rel=pick["path"])

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
    return build_preview(target, rel=rel_path)


def save_upload(
    task_dir: Path,
    *,
    filename: str,
    content_base64: str | None = None,
    text: str | None = None,
) -> dict[str, Any]:
    """Save an attachment under task_dir/attachments/."""
    root = Path(task_dir)
    att = root / "attachments"
    att.mkdir(parents=True, exist_ok=True)
    name = _safe_filename(filename)
    dest = att / name
    if content_base64 is not None:
        try:
            raw = base64.b64decode(content_base64, validate=False)
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": f"invalid base64: {exc}"}
    elif text is not None:
        raw = text.encode("utf-8")
    else:
        return {"ok": False, "error": "content_base64 or text required"}
    if len(raw) > _UPLOAD_MAX:
        return {"ok": False, "error": f"file exceeds {_UPLOAD_MAX} bytes"}
    dest.write_bytes(raw)
    return {
        "ok": True,
        "path": f"attachments/{name}",
        "bytes": len(raw),
        "ext": dest.suffix.lower(),
    }
