# SPDX-License-Identifier: MIT
"""File store for teach recordings and skill drafts."""

from __future__ import annotations

import json
from pathlib import Path

from .models import SkillDraft, TeachRecording


class TeachStore:
    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        self.recordings_dir = self.root / "recordings"
        self.drafts_dir = self.root / "drafts"
        self.recordings_dir.mkdir(parents=True, exist_ok=True)
        self.drafts_dir.mkdir(parents=True, exist_ok=True)

    def save_recording(self, recording: TeachRecording) -> Path:
        path = self.recordings_dir / f"{recording.id}.json"
        path.write_text(
            json.dumps(recording.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return path

    def load_recording(self, recording_id: str) -> TeachRecording:
        path = self.recordings_dir / f"{recording_id}.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        return TeachRecording.from_dict(data)

    def list_recordings(self) -> list[str]:
        return sorted(p.stem for p in self.recordings_dir.glob("*.json"))

    def save_draft(self, draft: SkillDraft) -> Path:
        path = self.drafts_dir / f"{draft.name}.json"
        path.write_text(
            json.dumps(draft.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return path

    def load_draft(self, name: str) -> SkillDraft:
        path = self.drafts_dir / f"{name}.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        return SkillDraft.from_dict(data)

    def list_drafts(self) -> list[str]:
        return sorted(p.stem for p in self.drafts_dir.glob("*.json"))

    def approve_draft(self, name: str) -> SkillDraft:
        draft = self.load_draft(name)
        draft.status = "approved"
        self.save_draft(draft)
        return draft
