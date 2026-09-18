# SPDX-License-Identifier: MIT
"""Parse SKILL.md frontmatter without PyYAML (python -S safe)."""

from __future__ import annotations

import re
from pathlib import Path

from .models import SkillMeta, SkillPackage

_FM_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n?(.*)$", re.DOTALL)
_KEY_RE = re.compile(r"^([A-Za-z0-9_-]+)\s*:\s*(.*)$")


def _unquote(s: str) -> str:
    s = s.strip()
    if len(s) >= 2 and ((s[0] == s[-1] == '"') or (s[0] == s[-1] == "'")):
        return s[1:-1]
    return s


def parse_frontmatter(text: str) -> tuple[dict[str, str], str]:
    """Return (frontmatter_dict, body). Missing frontmatter → ({}, full text)."""
    m = _FM_RE.match(text.lstrip("\ufeff"))
    if not m:
        return {}, text
    raw, body = m.group(1), m.group(2)
    meta: dict[str, str] = {}
    for line in raw.splitlines():
        line = line.rstrip()
        if not line or line.startswith("#"):
            continue
        km = _KEY_RE.match(line)
        if not km:
            continue
        key, val = km.group(1), _unquote(km.group(2))
        meta[key] = val
    return meta, body


def _split_tools(val: str) -> list[str]:
    if not val:
        return []
    # "Read,Write,Bash" or "[Read, Write]"
    val = val.strip().strip("[]")
    return [t.strip().strip("\"'") for t in re.split(r"[,，]", val) if t.strip()]


def parse_skill_file(path: Path, *, skill_id: str | None = None) -> SkillPackage:
    text = path.read_text(encoding="utf-8", errors="replace")
    fm, body = parse_frontmatter(text)
    sid = skill_id or path.parent.name
    name = fm.get("name") or sid
    meta = SkillMeta(
        id=sid,
        name=name,
        description=fm.get("description") or "",
        description_zh=fm.get("description_zh") or "",
        description_en=fm.get("description_en") or "",
        version=fm.get("version") or "",
        homepage=fm.get("homepage") or "",
        allowed_tools=_split_tools(fm.get("allowed-tools") or fm.get("allowed_tools") or ""),
        path=str(path),
        body_chars=len(body),
    )
    return SkillPackage(meta=meta, body=body)
