# SPDX-License-Identifier: MIT
"""Casdoor JWT verification client (stdlib, env-gated).

Verifies HS256 JWTs issued by Casdoor when ``OCTOP_CASDOOR_*`` is configured.
Does not replace Octop's auth middleware until explicitly wired; provides a
callable ``verify_access_token`` for enterprise integration.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any


def _env(name: str) -> str:
    return (os.environ.get(name) or "").strip()


def _b64url_decode(data: str) -> bytes:
    pad = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + pad)


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def casdoor_configured() -> bool:
    return bool(_env("OCTOP_CASDOOR_ENDPOINT") and _env("OCTOP_CASDOOR_CLIENT_ID"))


def decode_jwt_unverified(token: str) -> dict[str, Any]:
    parts = token.split(".")
    if len(parts) != 3:
        raise ValueError("malformed JWT")
    header = json.loads(_b64url_decode(parts[0]))
    payload = json.loads(_b64url_decode(parts[1]))
    return {"header": header, "payload": payload, "signature": parts[2]}


def verify_hs256(token: str, secret: str) -> dict[str, Any]:
    parts = token.split(".")
    if len(parts) != 3:
        raise ValueError("malformed JWT")
    signing_input = f"{parts[0]}.{parts[1]}".encode("ascii")
    expected = hmac.new(secret.encode("utf-8"), signing_input, hashlib.sha256).digest()
    given = _b64url_decode(parts[2])
    if not hmac.compare_digest(expected, given):
        raise ValueError("invalid JWT signature")
    payload = json.loads(_b64url_decode(parts[1]))
    now = int(time.time())
    exp = payload.get("exp")
    if isinstance(exp, (int, float)) and now > int(exp):
        raise ValueError("JWT expired")
    return payload


def verify_access_token(token: str) -> dict[str, Any]:
    """Verify token with client secret (HS256) when configured."""
    if not casdoor_configured():
        raise RuntimeError("Casdoor not configured (set OCTOP_CASDOOR_ENDPOINT + CLIENT_ID)")
    secret = _env("OCTOP_CASDOOR_CLIENT_SECRET")
    if not secret:
        # Allow decode-only inspection in soft mode
        decoded = decode_jwt_unverified(token)
        return {
            "verified": False,
            "reason": "OCTOP_CASDOOR_CLIENT_SECRET not set — payload decoded only",
            **decoded,
        }
    payload = verify_hs256(token, secret)
    return {"verified": True, "payload": payload}


def fetch_oidc_discovery() -> dict[str, Any]:
    endpoint = _env("OCTOP_CASDOOR_ENDPOINT").rstrip("/")
    if not endpoint:
        return {"ok": False, "error": "OCTOP_CASDOOR_ENDPOINT unset"}
    url = f"{endpoint}/.well-known/openid-configuration"
    try:
        req = urllib.request.Request(url, method="GET")
        req.add_header("User-Agent", "xiongbao-casdoor/1")
        with urllib.request.urlopen(req, timeout=5.0) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            data = json.loads(body) if body.strip().startswith("{") else {"raw": body[:500]}
            return {"ok": True, "url": url, "data": data}
    except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
        return {"ok": False, "url": url, "error": str(exc)[:300]}


def authorize_url(*, redirect_uri: str, state: str = "wb") -> str:
    endpoint = _env("OCTOP_CASDOOR_ENDPOINT").rstrip("/")
    client_id = _env("OCTOP_CASDOOR_CLIENT_ID")
    q = urllib.parse.urlencode(
        {
            "client_id": client_id,
            "response_type": "code",
            "redirect_uri": redirect_uri,
            "scope": "openid profile email",
            "state": state,
        }
    )
    return f"{endpoint}/login/oauth/authorize?{q}"
