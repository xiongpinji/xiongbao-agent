# SPDX-License-Identifier: MIT
"""Optional enterprise probes — Casdoor / Milvus (env-gated, no secrets in repo)."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any


def _env(name: str) -> str:
    return (os.environ.get(name) or "").strip()


def casdoor_status() -> dict[str, Any]:
    endpoint = _env("OCTOP_CASDOOR_ENDPOINT")
    client_id = _env("OCTOP_CASDOOR_CLIENT_ID")
    configured = bool(endpoint and client_id)
    reachable: bool | None = None
    detail = ""
    if endpoint:
        url = endpoint.rstrip("/") + "/"
        try:
            req = urllib.request.Request(url, method="GET")
            req.add_header("User-Agent", "xiongbao-enterprise-probe/1")
            with urllib.request.urlopen(req, timeout=3.0) as resp:
                reachable = int(getattr(resp, "status", 200) or 200) < 500
                detail = f"http {getattr(resp, 'status', '?')}"
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            reachable = False
            detail = str(exc)[:200]
    return {
        "provider": "casdoor",
        "configured": configured,
        "endpoint_set": bool(endpoint),
        "client_id_set": bool(client_id),
        "secret_set": bool(_env("OCTOP_CASDOOR_CLIENT_SECRET")),
        "reachable": reachable,
        "detail": detail,
        "wired": True,  # JWT verify client available via enterprise.casdoor
        "client": "octop.contrib.workbuddy.enterprise.casdoor",
    }


def milvus_status() -> dict[str, Any]:
    uri = _env("OCTOP_MILVUS_URI")
    configured = bool(uri)
    reachable: bool | None = None
    detail = ""
    if uri:
        # Prefer HTTP health-ish GET; many installs expose :9091 metrics — try base URI
        try:
            req = urllib.request.Request(uri.rstrip("/") + "/", method="GET")
            req.add_header("User-Agent", "xiongbao-enterprise-probe/1")
            token = _env("OCTOP_MILVUS_TOKEN")
            if token:
                req.add_header("Authorization", f"Bearer {token}")
            with urllib.request.urlopen(req, timeout=3.0) as resp:
                reachable = int(getattr(resp, "status", 200) or 200) < 500
                detail = f"http {getattr(resp, 'status', '?')}"
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            reachable = False
            detail = str(exc)[:200]
    return {
        "provider": "milvus",
        "configured": configured,
        "uri_set": bool(uri),
        "token_set": bool(_env("OCTOP_MILVUS_TOKEN")),
        "collection": _env("OCTOP_MILVUS_COLLECTION") or "",
        "reachable": reachable,
        "detail": detail,
        "wired": True,  # REST client available via enterprise.milvus
        "client": "octop.contrib.workbuddy.enterprise.milvus",
    }


def enterprise_probe() -> dict[str, Any]:
    return {"casdoor": casdoor_status(), "milvus": milvus_status()}


def enterprise_probe_json() -> str:
    return json.dumps(enterprise_probe(), ensure_ascii=False, indent=2)
