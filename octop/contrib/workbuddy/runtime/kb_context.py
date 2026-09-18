# SPDX-License-Identifier: MIT
"""KB search → prompt prefix for Task / Goal runs."""

from __future__ import annotations

from pathlib import Path

from ..knowledge import LocalKnowledgeBase


def kb_prompt_prefix(
    kb_root: Path | str,
    query: str,
    *,
    limit: int = 3,
    max_chars: int = 1200,
) -> str:
    root = Path(kb_root)
    if not root.is_dir():
        return ""
    kb = LocalKnowledgeBase(root)
    hits = kb.search(query, limit=limit)
    if not hits:
        return ""
    parts = ["[Knowledge recall]"]
    used = 0
    for h in hits:
        text = str(h.get("text") or "").strip()
        src = str(h.get("source") or "")
        chunk = f"- ({src}) {text}"
        if used + len(chunk) > max_chars:
            break
        parts.append(chunk)
        used += len(chunk)
    if len(parts) == 1:
        return ""
    return "\n".join(parts)
