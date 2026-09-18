# SPDX-License-Identifier: MIT
"""Project space — team-shared workspace + skill deposit (WorkBuddy parity)."""

from __future__ import annotations

import json
import shutil
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class ProjectMeta:
    project_id: str
    name: str
    created_at: str
    members: list[str] = field(default_factory=list)
    description: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ProjectSpace:
    """Filesystem-backed project space under ``<root>/<project_id>/``."""

    def __init__(self, root: Path | str) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _dir(self, project_id: str) -> Path:
        safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in project_id.strip())
        if not safe:
            raise ValueError("empty project_id")
        return self.root / safe

    def create(
        self,
        project_id: str,
        *,
        name: str = "",
        members: list[str] | None = None,
        description: str = "",
    ) -> ProjectMeta:
        d = self._dir(project_id)
        if d.exists():
            raise FileExistsError(f"project already exists: {project_id}")
        (d / "skills").mkdir(parents=True)
        (d / "shared").mkdir(parents=True)
        (d / "memory").mkdir(parents=True)
        meta = ProjectMeta(
            project_id=d.name,
            name=name or d.name,
            created_at=_utc(),
            members=list(members or []),
            description=description,
        )
        (d / "project.json").write_text(
            json.dumps(meta.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        (d / "memory" / "MEMORY.md").write_text("# Project memory\n", encoding="utf-8")
        return meta

    def load(self, project_id: str) -> ProjectMeta:
        path = self._dir(project_id) / "project.json"
        if not path.is_file():
            raise FileNotFoundError(f"project not found: {project_id}")
        data = json.loads(path.read_text(encoding="utf-8"))
        return ProjectMeta(
            project_id=data["project_id"],
            name=data.get("name") or data["project_id"],
            created_at=data.get("created_at") or "",
            members=list(data.get("members") or []),
            description=data.get("description") or "",
        )

    def list_projects(self) -> list[ProjectMeta]:
        rows: list[ProjectMeta] = []
        for p in sorted(self.root.iterdir()):
            if (p / "project.json").is_file():
                rows.append(self.load(p.name))
        return rows

    def deposit_skill(self, project_id: str, skill_src: Path | str) -> Path:
        """Copy a skill directory or SKILL.md into the project's skills/."""
        src = Path(skill_src)
        dest_root = self._dir(project_id) / "skills"
        dest_root.mkdir(parents=True, exist_ok=True)
        if src.is_dir():
            dest = dest_root / src.name
            if dest.exists():
                shutil.rmtree(dest)
            shutil.copytree(src, dest)
            return dest
        if src.is_file():
            dest = dest_root / src.name
            shutil.copy2(src, dest)
            return dest
        raise FileNotFoundError(str(src))

    def list_skills(self, project_id: str) -> list[str]:
        skills = self._dir(project_id) / "skills"
        if not skills.is_dir():
            return []
        return sorted(p.name for p in skills.iterdir())

    def shared_path(self, project_id: str) -> Path:
        p = self._dir(project_id) / "shared"
        p.mkdir(parents=True, exist_ok=True)
        return p

    def write_shared(self, project_id: str, relative: str, content: str) -> Path:
        base = self.shared_path(project_id)
        target = (base / relative).resolve()
        if not str(target).startswith(str(base.resolve())):
            raise ValueError("path escapes shared/")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return target
