# SPDX-License-Identifier: MIT
"""Create Task optionally bound to a git worktree."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..gitwork import WorktreeManager
from ..task import TaskRecord, TaskStore


def create_task_with_worktree(
    title: str,
    *,
    tasks_root: Path | str = "artifacts/tasks",
    repo: Path | str | None = None,
    worktrees_dir: Path | str | None = None,
    branch: str | None = None,
    mode: str = "craft",
    prompt: str = "",
    with_worktree: bool = False,
    dry_run: bool = True,
) -> dict[str, Any]:
    store = TaskStore(tasks_root)
    rec: TaskRecord = store.create(title, mode=mode, prompt=prompt)
    worktree_info: dict[str, Any] | None = None
    if with_worktree:
        repo_path = Path(repo) if repo else Path.cwd()
        wt_root = Path(worktrees_dir) if worktrees_dir else Path("artifacts/worktrees")
        mgr = WorktreeManager(repo_path, registry=wt_root / "registry.json")
        wt_path = wt_root / rec.task_id
        br = branch or f"wb/{rec.task_id}"
        info = mgr.create(wt_path, br, task_id=rec.task_id, dry_run=dry_run)
        worktree_info = info.to_dict()
        rec.meta = {**rec.meta, "worktree": worktree_info}
        path = store._path(rec.task_id)  # noqa: SLF001
        path.write_text(
            json.dumps(rec.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    return {"task": rec.to_dict(), "worktree": worktree_info}
