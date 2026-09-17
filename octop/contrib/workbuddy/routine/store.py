# SPDX-License-Identifier: MIT
"""Routine persistence (JSON files; SQLite can replace later)."""

from __future__ import annotations

import json
from pathlib import Path

from .models import Routine


class RoutineStore:
    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, routine_id: str) -> Path:
        return self.root / f"{routine_id}.json"

    def save(self, routine: Routine) -> Path:
        # Cap last_runs
        if len(routine.last_runs) > routine.keep_runs:
            routine.last_runs = routine.last_runs[-routine.keep_runs :]
        path = self._path(routine.id)
        path.write_text(
            json.dumps(routine.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return path

    def load(self, routine_id: str) -> Routine:
        data = json.loads(self._path(routine_id).read_text(encoding="utf-8"))
        return Routine.from_dict(data)

    def list_ids(self) -> list[str]:
        return sorted(p.stem for p in self.root.glob("*.json"))

    def list_for_bot(self, bot_id: str) -> list[Routine]:
        return [self.load(i) for i in self.list_ids() if self.load(i).bot_id == bot_id]

    def count_for_bot(self, bot_id: str) -> int:
        return sum(1 for i in self.list_ids() if self.load(i).bot_id == bot_id)

    def delete(self, routine_id: str) -> None:
        path = self._path(routine_id)
        if path.is_file():
            path.unlink()

    def delete_bot(self, bot_id: str) -> int:
        removed = 0
        for rid in list(self.list_ids()):
            r = self.load(rid)
            if r.bot_id == bot_id:
                self.delete(rid)
                removed += 1
        return removed
