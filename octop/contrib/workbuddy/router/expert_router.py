# SPDX-License-Identifier: MIT
"""Expert auto-router — match user query to converted library experts."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from ..bench.sample import default_library_root


@dataclass
class RouteHit:
    expert_id: str
    kind: str
    score: float
    reason: str
    category: str = ""

    def to_dict(self) -> dict:
        return {
            "expert_id": self.expert_id,
            "kind": self.kind,
            "score": self.score,
            "reason": self.reason,
            "category": self.category,
        }


def _tokens(text: str) -> list[str]:
    return [t for t in re.findall(r"[a-zA-Z0-9_\-]{2,}|[\u4e00-\u9fff]{2,}", (text or "").lower())]


class ExpertRouter:
    """Score experts by id / tags / category / welcome keywords."""

    def __init__(self, library: Path | None = None) -> None:
        self.library = Path(library) if library else default_library_root()
        self._rows: list[dict] = []
        self._loaded = False

    def load(self, *, force: bool = False) -> int:
        if self._loaded and not force:
            return len(self._rows)
        rows: list[dict] = []
        if not self.library.is_dir():
            self._rows = []
            self._loaded = True
            return 0
        for d in sorted(self.library.iterdir()):
            mj = d / "manifest.json"
            if not mj.is_file():
                continue
            try:
                m = json.loads(mj.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            wb = m.get("_wb") or {}
            kind = str(wb.get("expert_type") or m.get("kind") or "agent")
            tags = wb.get("tags") or m.get("tags") or []
            if isinstance(tags, dict):
                tag_list = [str(v) for v in tags.values()]
            else:
                tag_list = []
                for t in tags:
                    if isinstance(t, dict):
                        tag_list.append(str(t.get("zh") or t.get("en") or t))
                    else:
                        tag_list.append(str(t))
            cat = ""
            cl = wb.get("category_label") or {}
            if isinstance(cl, dict):
                cat = str(cl.get("zh") or cl.get("en") or "")
            elif cl:
                cat = str(cl)
            welcome = m.get("welcome_message") or {}
            if isinstance(welcome, dict):
                welcome_s = str(welcome.get("zh") or welcome.get("en") or "")
            else:
                welcome_s = str(welcome or "")
            blob = " ".join(
                [
                    d.name.lower(),
                    " ".join(t.lower() for t in tag_list),
                    cat.lower(),
                    welcome_s.lower(),
                    str(wb.get("category_id") or "").lower(),
                ]
            )
            rows.append(
                {
                    "expert_id": d.name,
                    "kind": kind,
                    "category": cat,
                    "tags": tag_list,
                    "blob": blob,
                    "dir": str(d),
                }
            )
        self._rows = rows
        self._loaded = True
        return len(rows)

    def route(self, query: str, *, limit: int = 5, kind: str | None = None) -> list[RouteHit]:
        self.load()
        q = (query or "").strip().lower()
        if not q:
            return []
        q_tokens = _tokens(q)
        hits: list[RouteHit] = []
        for row in self._rows:
            if kind and row["kind"] != kind:
                continue
            score = 0.0
            reasons: list[str] = []
            eid = row["expert_id"].lower()
            if q in eid or eid in q:
                score += 20
                reasons.append("id")
            if q in row["blob"]:
                score += 8
                reasons.append("blob")
            for t in q_tokens:
                if t in eid:
                    score += 4
                if t in row["blob"]:
                    score += 1.5
                for tag in row["tags"]:
                    if t in str(tag).lower():
                        score += 3
                        reasons.append(f"tag:{tag}")
            if score <= 0:
                continue
            hits.append(
                RouteHit(
                    expert_id=row["expert_id"],
                    kind=row["kind"],
                    score=score,
                    reason=",".join(dict.fromkeys(reasons)) or "token",
                    category=row["category"],
                )
            )
        hits.sort(key=lambda h: (-h.score, h.expert_id))
        return hits[:limit]
