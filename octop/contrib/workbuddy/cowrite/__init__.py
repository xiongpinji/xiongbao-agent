# SPDX-License-Identifier: MIT
"""Human–AI cowriting session store."""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class CowriteTurn:
    author: str  # human | assistant
    text: str
    ts: str = field(default_factory=_utc)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class CowriteSession:
    session_id: str
    title: str
    created_at: str
    updated_at: str
    document: str = ""
    turns: list[CowriteTurn] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "title": self.title,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "document": self.document,
            "turns": [t.to_dict() for t in self.turns],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CowriteSession:
        turns = [
            CowriteTurn(
                author=str(t.get("author") or "human"),
                text=str(t.get("text") or ""),
                ts=str(t.get("ts") or ""),
            )
            for t in (data.get("turns") or [])
            if isinstance(t, dict)
        ]
        return cls(
            session_id=str(data["session_id"]),
            title=str(data.get("title") or data["session_id"]),
            created_at=str(data.get("created_at") or ""),
            updated_at=str(data.get("updated_at") or ""),
            document=str(data.get("document") or ""),
            turns=turns,
        )


class CowriteStore:
    def __init__(self, root: Path | str) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, session_id: str) -> Path:
        return self.root / f"{session_id}.json"

    def start(self, title: str, *, seed: str = "") -> CowriteSession:
        sid = f"cw-{uuid.uuid4().hex[:10]}"
        now = _utc()
        session = CowriteSession(
            session_id=sid,
            title=title,
            created_at=now,
            updated_at=now,
            document=seed,
        )
        self._save(session)
        return session

    def _save(self, session: CowriteSession) -> None:
        self._path(session.session_id).write_text(
            json.dumps(session.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def get(self, session_id: str) -> CowriteSession:
        path = self._path(session_id)
        if not path.is_file():
            raise FileNotFoundError(f"session not found: {session_id}")
        return CowriteSession.from_dict(json.loads(path.read_text(encoding="utf-8")))

    def append(
        self,
        session_id: str,
        author: str,
        text: str,
        *,
        apply_to_document: bool = True,
    ) -> CowriteSession:
        session = self.get(session_id)
        session.turns.append(CowriteTurn(author=author, text=text))
        if apply_to_document and text.strip():
            if session.document and not session.document.endswith("\n"):
                session.document += "\n"
            session.document += text.strip() + "\n"
        session.updated_at = _utc()
        self._save(session)
        return session

    def export_markdown(self, session_id: str, dest: Path | str) -> Path:
        session = self.get(session_id)
        out = Path(dest)
        out.parent.mkdir(parents=True, exist_ok=True)
        lines = [f"# {session.title}", "", session.document.strip(), "", "## Turns", ""]
        for t in session.turns:
            lines.append(f"- **{t.author}** ({t.ts}): {t.text[:200]}")
        out.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return out
