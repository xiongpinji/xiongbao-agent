# SPDX-License-Identifier: MIT
"""SkillHub data models."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class SkillMeta:
    """Parsed SKILL.md frontmatter + path info."""

    id: str
    name: str
    description: str = ""
    description_zh: str = ""
    description_en: str = ""
    version: str = ""
    homepage: str = ""
    allowed_tools: list[str] = field(default_factory=list)
    path: str = ""
    body_chars: int = 0
    requires_hint: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def search_blob(self) -> str:
        parts = [
            self.id,
            self.name,
            self.description,
            self.description_zh,
            self.description_en,
            " ".join(self.allowed_tools),
        ]
        return " ".join(p for p in parts if p).lower()


@dataclass
class SkillPackage:
    """Full skill: meta + markdown body (without frontmatter)."""

    meta: SkillMeta
    body: str

    def to_dict(self, *, include_body: bool = True) -> dict[str, Any]:
        d = {"meta": self.meta.to_dict()}
        if include_body:
            d["body"] = self.body
            d["body_preview"] = self.body[:400]
        return d

    def system_prompt(self, *, max_chars: int = 12000) -> str:
        header = (
            f"# Skill: {self.meta.name}\n"
            f"id={self.meta.id} version={self.meta.version or 'n/a'}\n\n"
            f"{self.meta.description_zh or self.meta.description}\n\n"
        )
        body = self.body.strip()
        text = header + body
        if len(text) <= max_chars:
            return text
        return text[: max_chars - 80] + "\n\n…[skill truncated for context budget]…"
