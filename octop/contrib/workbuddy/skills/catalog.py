# SPDX-License-Identifier: MIT
"""Skill catalog — scan vendor/workbuddyskills/skills and search."""

from __future__ import annotations

import json
import re
from pathlib import Path

from .models import SkillMeta, SkillPackage
from .parser import parse_skill_file


def default_skills_root(project_root: Path | None = None) -> Path:
    # skills/catalog.py → workbuddy → contrib → octop → project
    root = project_root or Path(__file__).resolve().parents[4]
    return root / "vendor" / "workbuddyskills" / "skills"


def default_builtin_skills_root(project_root: Path | None = None) -> Path:
    root = project_root or Path(__file__).resolve().parents[4]
    return root / "vendor" / "workbuddy-experts" / "builtin-skills"


class SkillCatalog:
    """In-memory index of SkillMeta (lazy-load full body on demand)."""

    def __init__(
        self,
        skills_root: Path | None = None,
        *,
        extra_roots: list[Path] | None = None,
        include_builtin: bool | None = None,
    ) -> None:
        # Custom root (tests / overrides): skip builtin unless explicitly requested.
        # Default root: include vendor builtin-skills (skill-creator, …).
        explicit_root = skills_root is not None
        self.skills_root = Path(skills_root) if skills_root else default_skills_root()
        if include_builtin is None:
            include_builtin = not explicit_root
        extras: list[Path] = []
        if include_builtin:
            extras.append(default_builtin_skills_root())
        if extra_roots:
            extras.extend(Path(p) for p in extra_roots)
        self.extra_roots = extras
        self.include_builtin = bool(include_builtin)
        self._index: dict[str, SkillMeta] = {}
        self._scanned = False

    def _scan_root(self, root: Path) -> None:
        if not root.is_dir():
            return
        for child in sorted(root.iterdir()):
            if not child.is_dir():
                continue
            skill_md = child / "SKILL.md"
            if not skill_md.is_file():
                continue
            try:
                pkg = parse_skill_file(skill_md, skill_id=child.name)
            except OSError:
                continue
            # First root wins on id collision (skills/ over builtin)
            if pkg.meta.id in self._index:
                continue
            self._index[pkg.meta.id] = pkg.meta

    def scan(self, *, force: bool = False) -> int:
        if self._scanned and not force:
            return len(self._index)
        self._index.clear()
        self._scan_root(self.skills_root)
        for root in self.extra_roots:
            self._scan_root(root)
        self._scanned = True
        return len(self._index)

    def list(self) -> list[SkillMeta]:
        self.scan()
        return sorted(self._index.values(), key=lambda m: m.id)

    def get_meta(self, skill_id: str) -> SkillMeta | None:
        self.scan()
        return self._index.get(skill_id)

    def load(self, skill_id: str) -> SkillPackage:
        self.scan()
        meta = self._index.get(skill_id)
        if meta is None:
            raise KeyError(f"skill not found: {skill_id}")
        path = Path(meta.path)
        if not path.is_file():
            path = self.skills_root / skill_id / "SKILL.md"
        return parse_skill_file(path, skill_id=skill_id)

    def search(self, query: str, *, limit: int = 20) -> list[SkillMeta]:
        self.scan()
        q = (query or "").strip().lower()
        if not q:
            return self.list()[:limit]
        tokens = [t for t in re_split_tokens(q) if t]
        scored: list[tuple[int, SkillMeta]] = []
        for meta in self._index.values():
            blob = meta.search_blob()
            score = 0
            if q in blob:
                score += 10
            if q == meta.id.lower() or q == meta.name.lower():
                score += 50
            for t in tokens:
                if t in blob:
                    score += 3
                if t in meta.id.lower():
                    score += 5
            if score:
                scored.append((score, meta))
        scored.sort(key=lambda x: (-x[0], x[1].id))
        return [m for _, m in scored[:limit]]

    def to_json_index(self) -> list[dict]:
        return [m.to_dict() for m in self.list()]

    def write_index(self, path: Path) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(self.to_json_index(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return path


def re_split_tokens(q: str) -> list[str]:
    return re.split(r"[\s,/|]+", q)
