# SPDX-License-Identifier: MIT
"""Persist GoalRun JSON under a root directory."""

from __future__ import annotations

import json
from pathlib import Path

from .models import GoalRun


class GoalStore:
    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.runs_dir = self.root / "runs"
        self.runs_dir.mkdir(parents=True, exist_ok=True)

    def save_run(self, run: GoalRun) -> Path:
        path = self.runs_dir / f"{run.id}.json"
        path.write_text(json.dumps(run.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
        return path

    def list_runs(self) -> list[str]:
        return sorted(p.stem for p in self.runs_dir.glob("*.json"))
