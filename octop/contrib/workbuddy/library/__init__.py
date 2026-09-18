# SPDX-License-Identifier: MIT
"""Content library index + lightweight static publish."""

from __future__ import annotations

import hashlib
import json
import shutil
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class LibraryEntry:
    entry_id: str
    path: str
    title: str
    size: int
    sha256: str
    indexed_at: str
    tags: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class LibraryIndex:
    def __init__(self, root: Path | str) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.index_path = self.root / "index.json"
        self.content_dir = self.root / "content"
        self.content_dir.mkdir(parents=True, exist_ok=True)
        self.publish_dir = self.root / "publish"
        self.publish_dir.mkdir(parents=True, exist_ok=True)

    def _load(self) -> dict[str, Any]:
        if not self.index_path.is_file():
            return {"entries": {}}
        data = json.loads(self.index_path.read_text(encoding="utf-8"))
        data.setdefault("entries", {})
        return data

    def _save(self, data: dict[str, Any]) -> None:
        self.index_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def add_file(
        self,
        src: Path | str,
        *,
        title: str = "",
        tags: list[str] | None = None,
        entry_id: str | None = None,
    ) -> LibraryEntry:
        path = Path(src)
        if not path.is_file():
            raise FileNotFoundError(str(path))
        raw = path.read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        eid = entry_id or digest[:12]
        dest = self.content_dir / f"{eid}{path.suffix}"
        shutil.copy2(path, dest)
        entry = LibraryEntry(
            entry_id=eid,
            path=str(dest.relative_to(self.root).as_posix()),
            title=title or path.name,
            size=len(raw),
            sha256=digest,
            indexed_at=_utc(),
            tags=list(tags or []),
        )
        data = self._load()
        data["entries"][eid] = entry.to_dict()
        self._save(data)
        return entry

    def list_entries(self) -> list[LibraryEntry]:
        data = self._load()
        out: list[LibraryEntry] = []
        for row in (data.get("entries") or {}).values():
            if isinstance(row, dict):
                out.append(
                    LibraryEntry(
                        entry_id=str(row["entry_id"]),
                        path=str(row.get("path") or ""),
                        title=str(row.get("title") or ""),
                        size=int(row.get("size") or 0),
                        sha256=str(row.get("sha256") or ""),
                        indexed_at=str(row.get("indexed_at") or ""),
                        tags=list(row.get("tags") or []),
                    )
                )
        return sorted(out, key=lambda e: e.entry_id)

    def publish(self, *, site_title: str = "WorkBuddy Library") -> Path:
        entries = self.list_entries()
        lines = [
            "<!DOCTYPE html>",
            f"<html><head><meta charset='utf-8'><title>{site_title}</title>",
            "<style>body{font-family:system-ui;margin:2rem}li{margin:.4rem 0}</style>",
            "</head><body>",
            f"<h1>{site_title}</h1>",
            f"<p>{len(entries)} entries · generated {_utc()}</p>",
            "<ul>",
        ]
        for e in entries:
            lines.append(f"<li><strong>{e.title}</strong> — {e.path} ({e.size} B)</li>")
        lines.extend(["</ul>", "</body></html>"])
        out = self.publish_dir / "index.html"
        out.write_text("\n".join(lines), encoding="utf-8")
        # copy content for static serve
        pub_content = self.publish_dir / "content"
        if pub_content.exists():
            shutil.rmtree(pub_content)
        if self.content_dir.is_dir():
            shutil.copytree(self.content_dir, pub_content)
        return out
