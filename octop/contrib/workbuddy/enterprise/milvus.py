# SPDX-License-Identifier: MIT
"""Milvus REST-ish client for RAG (env-gated, stdlib).

Uses Milvus HTTP API when available (``/v2/vectordb/...`` style) or falls back
to documenting gRPC-only installs. No pymilvus dependency required.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any


def _env(name: str) -> str:
    return (os.environ.get(name) or "").strip()


def milvus_configured() -> bool:
    return bool(_env("OCTOP_MILVUS_URI"))


def default_collection() -> str:
    """Prefer tenant-scoped ``wb_<tid>`` when ``WB_TENANT_ID`` is set."""
    tid = _env("WB_TENANT_ID")
    if tid:
        from ..tenant.milvus_ns import tenant_collection

        return tenant_collection(tid)
    return _env("OCTOP_MILVUS_COLLECTION") or "wb_memory"


def _headers() -> dict[str, str]:
    h = {
        "Content-Type": "application/json",
        "User-Agent": "xiongbao-milvus/1",
    }
    token = _env("OCTOP_MILVUS_TOKEN")
    if token:
        h["Authorization"] = f"Bearer {token}"
    return h


def _post(path: str, body: dict[str, Any], *, timeout: float = 10.0) -> dict[str, Any]:
    uri = _env("OCTOP_MILVUS_URI").rstrip("/")
    if not uri:
        raise RuntimeError("OCTOP_MILVUS_URI unset")
    url = uri + path
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST", headers=_headers())
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            parsed: Any
            try:
                parsed = json.loads(raw) if raw else {}
            except json.JSONDecodeError:
                parsed = {"raw": raw[:500]}
            return {"ok": True, "status": getattr(resp, "status", 200), "data": parsed, "url": url}
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return {"ok": False, "error": str(exc)[:300], "url": url}


def list_collections() -> dict[str, Any]:
    """Best-effort list via HTTP v2 API."""
    return _post(
        "/v2/vectordb/collections/list",
        {"dbName": _env("OCTOP_MILVUS_DB") or "default"},
    )


def search(
    vector: list[float],
    *,
    collection: str | None = None,
    top_k: int = 5,
    output_fields: list[str] | None = None,
) -> dict[str, Any]:
    coll = collection or default_collection()
    body: dict[str, Any] = {
        "collectionName": coll,
        "data": [vector],
        "limit": top_k,
        "outputFields": output_fields or ["text", "source"],
    }
    return _post("/v2/vectordb/entities/search", body)


def upsert_texts(
    rows: list[dict[str, Any]],
    *,
    collection: str | None = None,
) -> dict[str, Any]:
    """Upsert pre-embedded rows: each row needs ``vector`` + metadata fields."""
    coll = collection or default_collection()
    return _post(
        "/v2/vectordb/entities/insert",
        {"collectionName": coll, "data": rows},
    )


def rag_status() -> dict[str, Any]:
    configured = milvus_configured()
    result: dict[str, Any] = {
        "configured": configured,
        "uri": _env("OCTOP_MILVUS_URI"),
        "collection": default_collection(),
        "wired": True,
    }
    if configured:
        result["list_collections"] = list_collections()
    return result
