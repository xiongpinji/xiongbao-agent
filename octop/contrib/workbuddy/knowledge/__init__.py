# SPDX-License-Identifier: MIT
"""Local knowledge base — directory chunk ingest + lexical search (+ optional Milvus)."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _chunk_text(text: str, *, size: int = 800, overlap: int = 100) -> list[str]:
    text = text.strip()
    if not text:
        return []
    if len(text) <= size:
        return [text]
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(len(text), start + size)
        chunks.append(text[start:end])
        if end >= len(text):
            break
        start = max(0, end - overlap)
    return chunks


@dataclass
class KnowledgeChunk:
    chunk_id: str
    source: str
    text: str
    indexed_at: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class LocalKnowledgeBase:
    def __init__(self, root: Path | str) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.store_path = self.root / "chunks.jsonl"

    def ingest_file(self, path: Path | str, *, chunk_size: int = 800) -> list[KnowledgeChunk]:
        src = Path(path)
        if not src.is_file():
            raise FileNotFoundError(str(src))
        text = src.read_text(encoding="utf-8", errors="replace")
        chunks = _chunk_text(text, size=chunk_size)
        out: list[KnowledgeChunk] = []
        with self.store_path.open("a", encoding="utf-8") as fh:
            for i, part in enumerate(chunks):
                digest = hashlib.sha256(f"{src}:{i}:{part}".encode("utf-8")).hexdigest()[:16]
                row = KnowledgeChunk(
                    chunk_id=digest,
                    source=str(src),
                    text=part,
                    indexed_at=_utc(),
                )
                fh.write(json.dumps(row.to_dict(), ensure_ascii=False) + "\n")
                out.append(row)
        return out

    def ingest_dir(self, directory: Path | str, *, glob: str = "**/*.md") -> int:
        root = Path(directory)
        count = 0
        for path in sorted(root.glob(glob)):
            if path.is_file():
                count += len(self.ingest_file(path))
        return count

    def _iter_chunks(self) -> list[KnowledgeChunk]:
        if not self.store_path.is_file():
            return []
        rows: list[KnowledgeChunk] = []
        for line in self.store_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                continue
            rows.append(
                KnowledgeChunk(
                    chunk_id=str(data.get("chunk_id") or ""),
                    source=str(data.get("source") or ""),
                    text=str(data.get("text") or ""),
                    indexed_at=str(data.get("indexed_at") or ""),
                )
            )
        return rows

    def search(self, query: str, *, limit: int = 5) -> list[dict[str, Any]]:
        tokens = [t for t in re.split(r"\W+", query.lower()) if t]
        scored: list[tuple[int, KnowledgeChunk]] = []
        for chunk in self._iter_chunks():
            hay = chunk.text.lower()
            score = sum(1 for t in tokens if t in hay)
            if score:
                scored.append((score, chunk))
        scored.sort(key=lambda x: (-x[0], x[1].chunk_id))
        return [
            {"score": s, "chunk_id": c.chunk_id, "source": c.source, "text": c.text[:400]}
            for s, c in scored[:limit]
        ]

    def upsert_milvus_dry(self, *, collection: str = "wb_kb") -> dict[str, Any]:
        """Prepare a Milvus upsert payload without requiring a live cluster."""
        chunks = self._iter_chunks()
        return {
            "collection": collection,
            "count": len(chunks),
            "dry_run": True,
            "sample_ids": [c.chunk_id for c in chunks[:5]],
        }
