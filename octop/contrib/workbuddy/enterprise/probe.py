# SPDX-License-Identifier: MIT
"""Optional enterprise probes — Casdoor / Milvus (env-gated, no secrets in repo)."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any
from urllib.parse import urlparse


def _env(name: str) -> str:
    return (os.environ.get(name) or "").strip()


def _http_probe(url: str, *, token: str = "", timeout: float = 3.0) -> tuple[bool | None, str]:
    try:
        req = urllib.request.Request(url, method="GET")
        req.add_header("User-Agent", "xiongbao-enterprise-probe/1")
        if token:
            req.add_header("Authorization", f"Bearer {token}")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            code = int(getattr(resp, "status", 200) or 200)
            return code < 500, f"http {code} @ {url}"
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return False, f"{url}: {str(exc)[:160]}"


def casdoor_status() -> dict[str, Any]:
    endpoint = _env("OCTOP_CASDOOR_ENDPOINT")
    client_id = _env("OCTOP_CASDOOR_CLIENT_ID")
    configured = bool(endpoint and client_id)
    reachable: bool | None = None
    detail = ""
    if endpoint:
        base = endpoint.rstrip("/")
        for url in (base + "/", base + "/api/health", base + "/swagger"):
            reachable, detail = _http_probe(url)
            if reachable:
                break
    return {
        "provider": "casdoor",
        "configured": configured,
        "endpoint_set": bool(endpoint),
        "client_id_set": bool(client_id),
        "secret_set": bool(_env("OCTOP_CASDOOR_CLIENT_SECRET")),
        "reachable": reachable,
        "detail": detail,
        "wired": True,
        "client": "octop.contrib.workbuddy.enterprise.casdoor",
    }


def _milvus_candidates(uri: str) -> list[str]:
    """Build health URLs from gRPC or HTTP milvus URI."""
    raw = uri.rstrip("/")
    urls = [raw + "/", raw + "/healthz", raw + "/api/v1/health"]
    parsed = urlparse(raw if "://" in raw else "http://" + raw)
    host = parsed.hostname or "127.0.0.1"
    # standalone metrics often on 9091
    urls.extend(
        [
            f"http://{host}:9091/healthz",
            f"http://{host}:9091/",
        ]
    )
    # de-dupe preserve order
    seen: set[str] = set()
    out: list[str] = []
    for u in urls:
        if u not in seen:
            seen.add(u)
            out.append(u)
    return out


def milvus_status() -> dict[str, Any]:
    uri = _env("OCTOP_MILVUS_URI")
    configured = bool(uri)
    reachable: bool | None = None
    detail = ""
    if uri:
        token = _env("OCTOP_MILVUS_TOKEN")
        for url in _milvus_candidates(uri):
            reachable, detail = _http_probe(url, token=token)
            if reachable:
                break
    return {
        "provider": "milvus",
        "configured": configured,
        "uri_set": bool(uri),
        "token_set": bool(_env("OCTOP_MILVUS_TOKEN")),
        "collection": _env("OCTOP_MILVUS_COLLECTION") or "",
        "reachable": reachable,
        "detail": detail,
        "wired": True,
        "client": "octop.contrib.workbuddy.enterprise.milvus",
    }


def enterprise_probe() -> dict[str, Any]:
    return {"casdoor": casdoor_status(), "milvus": milvus_status()}


def enterprise_probe_json() -> str:
    return json.dumps(enterprise_probe(), ensure_ascii=False, indent=2)
