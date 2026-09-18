# SPDX-License-Identifier: MIT
"""Inspiration templates + Buddy App scaffold."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

BUILTIN_TEMPLATES: dict[str, dict[str, Any]] = {
    "daily-brief": {
        "title": "每日简报",
        "description": "汇总日历与待办，生成晨间简报",
        "files": {
            "SOUL.md": "# Daily Brief Buddy\n汇总今日重点并输出简报。\n",
            "SKILL.md": "---\nname: daily-brief\ndescription: morning brief\n---\n# Daily Brief\n",
        },
    },
    "meeting-notes": {
        "title": "会议纪要",
        "description": "从录音/文字整理会议纪要",
        "files": {
            "SOUL.md": "# Meeting Notes Buddy\n整理会议要点、决策与待办。\n",
            "SKILL.md": "---\nname: meeting-notes\ndescription: meeting notes\n---\n# Meeting Notes\n",
        },
    },
    "research-digest": {
        "title": "研究摘要",
        "description": "把多篇资料压缩成结构化摘要",
        "files": {
            "SOUL.md": "# Research Digest Buddy\n提炼论点与证据。\n",
            "SKILL.md": "---\nname: research-digest\ndescription: research digest\n---\n# Research Digest\n",
        },
    },
}


class InspirationCatalog:
    def __init__(self, root: Path | str | None = None) -> None:
        self.root = Path(root) if root else None
        self._extra: dict[str, dict[str, Any]] = {}
        if self.root and (self.root / "catalog.json").is_file():
            data = json.loads((self.root / "catalog.json").read_text(encoding="utf-8"))
            if isinstance(data, dict):
                self._extra = {str(k): v for k, v in data.items() if isinstance(v, dict)}

    def list(self) -> list[dict[str, Any]]:
        merged = {**BUILTIN_TEMPLATES, **self._extra}
        return [
            {"id": k, "title": v.get("title", k), "description": v.get("description", "")}
            for k, v in sorted(merged.items())
        ]

    def get(self, template_id: str) -> dict[str, Any]:
        merged = {**BUILTIN_TEMPLATES, **self._extra}
        if template_id not in merged:
            raise FileNotFoundError(f"template not found: {template_id}")
        return merged[template_id]

    def scaffold(self, template_id: str, dest: Path | str) -> Path:
        tpl = self.get(template_id)
        target = Path(dest)
        if target.exists() and any(target.iterdir()):
            raise FileExistsError(f"dest not empty: {target}")
        target.mkdir(parents=True, exist_ok=True)
        files = tpl.get("files") or {}
        for rel, content in files.items():
            path = target / str(rel)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(str(content), encoding="utf-8")
        meta = {
            "template_id": template_id,
            "title": tpl.get("title"),
            "description": tpl.get("description"),
        }
        (target / "buddy.json").write_text(
            json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return target
