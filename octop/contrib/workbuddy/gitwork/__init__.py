# SPDX-License-Identifier: MIT
"""Git worktree helper for parallel task isolation."""

from __future__ import annotations

import json
import subprocess
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class WorktreeInfo:
    path: str
    branch: str
    created_at: str
    task_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class WorktreeManager:
    """Track worktrees under a registry file; optionally invoke ``git worktree``."""

    def __init__(self, repo: Path | str, registry: Path | str | None = None) -> None:
        self.repo = Path(repo)
        self.registry = Path(registry) if registry else self.repo / ".wb-worktrees.json"

    def _load(self) -> list[dict[str, Any]]:
        if not self.registry.is_file():
            return []
        data = json.loads(self.registry.read_text(encoding="utf-8"))
        return list(data) if isinstance(data, list) else []

    def _save(self, rows: list[dict[str, Any]]) -> None:
        self.registry.parent.mkdir(parents=True, exist_ok=True)
        self.registry.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")

    def list(self) -> list[WorktreeInfo]:
        return [WorktreeInfo(**r) for r in self._load() if isinstance(r, dict) and "path" in r]

    def create(
        self,
        path: Path | str,
        branch: str,
        *,
        task_id: str = "",
        dry_run: bool = False,
        base_ref: str = "HEAD",
    ) -> WorktreeInfo:
        dest = Path(path)
        info = WorktreeInfo(
            path=str(dest.resolve()) if dest.exists() or not dry_run else str(dest),
            branch=branch,
            created_at=_utc(),
            task_id=task_id,
        )
        if not dry_run:
            dest.parent.mkdir(parents=True, exist_ok=True)
            cmd = [
                "git",
                "-C",
                str(self.repo),
                "worktree",
                "add",
                "-b",
                branch,
                str(dest),
                base_ref,
            ]
            # If branch already exists, fall back to attach without -b
            proc = subprocess.run(cmd, capture_output=True, text=True)
            if proc.returncode != 0:
                cmd2 = ["git", "-C", str(self.repo), "worktree", "add", str(dest), branch]
                proc2 = subprocess.run(cmd2, capture_output=True, text=True)
                if proc2.returncode != 0:
                    raise RuntimeError(
                        f"git worktree failed: {proc.stderr or proc2.stderr}".strip()
                    )
            info = WorktreeInfo(
                path=str(dest.resolve()),
                branch=branch,
                created_at=_utc(),
                task_id=task_id,
            )
        rows = self._load()
        rows.append(info.to_dict())
        self._save(rows)
        return info

    def remove(self, path: Path | str, *, dry_run: bool = False, force: bool = False) -> bool:
        target = str(Path(path).resolve() if Path(path).exists() else Path(path))
        rows = self._load()
        kept = [r for r in rows if str(r.get("path")) != target and str(r.get("path")) != str(path)]
        removed = len(kept) != len(rows)
        if not dry_run and Path(path).exists():
            cmd = ["git", "-C", str(self.repo), "worktree", "remove", str(path)]
            if force:
                cmd.append("--force")
            subprocess.run(cmd, capture_output=True, text=True)
        self._save(kept)
        return removed

    def register_only(self, path: str, branch: str, *, task_id: str = "") -> WorktreeInfo:
        """Record a logical parallel workspace without calling git (tests / dry)."""
        return self.create(path, branch, task_id=task_id, dry_run=True)
