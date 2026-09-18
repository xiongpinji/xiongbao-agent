# SPDX-License-Identifier: MIT
"""Load WorkBuddy-style workspace identity / memory files."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class WorkspaceMemory:
    root: Path
    soul: str = ""
    user: str = ""
    identity: str = ""
    durable: str = ""
    daily: str = ""
    paths: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "root": str(self.root),
            "soul_chars": len(self.soul),
            "user_chars": len(self.user),
            "identity_chars": len(self.identity),
            "durable_chars": len(self.durable),
            "daily_chars": len(self.daily),
            "paths": dict(self.paths),
        }


def _read(path: Path, *, max_chars: int) -> str:
    if not path.is_file():
        return ""
    try:
        return path.read_text(encoding="utf-8", errors="replace")[:max_chars]
    except OSError:
        return ""


def load_workspace_memory(
    root: Path | str,
    *,
    max_chars: int = 8000,
    daily_name: str | None = None,
) -> WorkspaceMemory:
    """Load SOUL.md / USER.md / IDENTITY.md / MEMORY.md / memory/*.md."""
    root_p = Path(root)
    mem = WorkspaceMemory(root=root_p)
    mapping = {
        "soul": root_p / "SOUL.md",
        "user": root_p / "USER.md",
        "identity": root_p / "IDENTITY.md",
        "durable": root_p / "MEMORY.md",
    }
    for key, path in mapping.items():
        text = _read(path, max_chars=max_chars)
        setattr(mem, key if key != "durable" else "durable", text)
        if text:
            mem.paths[key] = str(path)

    daily_dir = root_p / "memory"
    if daily_dir.is_dir():
        if daily_name:
            candidate = daily_dir / daily_name
        else:
            days = sorted(daily_dir.glob("????-??-??.md"), reverse=True)
            candidate = days[0] if days else None
        if candidate is not None and candidate.is_file():
            mem.daily = _read(candidate, max_chars=max_chars)
            mem.paths["daily"] = str(candidate)
    return mem
