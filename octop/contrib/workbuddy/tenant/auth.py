# SPDX-License-Identifier: MIT
"""Console / API JWT for multi-tenant auth (stdlib HS256)."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
from typing import Any

from .models import TenantContext


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(data: str) -> bytes:
    pad = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + pad)


def console_secret() -> str:
    secret = (os.environ.get("WB_CONSOLE_SECRET") or "").strip()
    if secret:
        return secret
    # Dev fallback — must be overridden in production
    return "wb-dev-secret-change-me"


def auth_required() -> bool:
    flag = (os.environ.get("WB_CONSOLE_AUTH") or os.environ.get("WB_MULTI_TENANT") or "").strip()
    return flag in {"1", "true", "yes"}


def issue_token(ctx: TenantContext, *, ttl_sec: int = 7200) -> str:
    header = {"alg": "HS256", "typ": "JWT"}
    now = int(time.time())
    payload = {
        "tid": ctx.tenant_id,
        "uid": ctx.user_id,
        "role": ctx.role,
        "iat": now,
        "exp": now + int(ttl_sec),
        "iss": "wb-console",
    }
    h = _b64url_encode(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    p = _b64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signing_input = f"{h}.{p}".encode("ascii")
    sig = hmac.new(console_secret().encode("utf-8"), signing_input, hashlib.sha256).digest()
    return f"{h}.{p}.{_b64url_encode(sig)}"


def verify_token(token: str) -> TenantContext:
    parts = token.split(".")
    if len(parts) != 3:
        raise ValueError("malformed token")
    signing_input = f"{parts[0]}.{parts[1]}".encode("ascii")
    expected = hmac.new(console_secret().encode("utf-8"), signing_input, hashlib.sha256).digest()
    given = _b64url_decode(parts[2])
    if not hmac.compare_digest(expected, given):
        raise ValueError("invalid signature")
    payload = json.loads(_b64url_decode(parts[1]))
    now = int(time.time())
    exp = payload.get("exp")
    if isinstance(exp, (int, float)) and now > int(exp):
        raise ValueError("token expired")
    tid = str(payload.get("tid") or "").strip()
    uid = str(payload.get("uid") or "").strip()
    if not tid or not uid:
        raise ValueError("missing tid/uid")
    return TenantContext(tenant_id=tid, user_id=uid, role=str(payload.get("role") or "user"))


def parse_bearer(authorization: str | None) -> str | None:
    if not authorization:
        return None
    parts = authorization.strip().split(None, 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None
    return parts[1].strip() or None


def exchange_casdoor_token(casdoor_jwt: str) -> TenantContext:
    """Map Casdoor claims → TenantContext when Casdoor is configured.

    Expects claims: ``tenant``/``tid`` and ``name``/``sub``/``uid``.
    """
    from ..enterprise.casdoor import decode_jwt_unverified, verify_access_token

    result = verify_access_token(casdoor_jwt)
    payload: dict[str, Any]
    if result.get("verified") and isinstance(result.get("payload"), dict):
        payload = dict(result["payload"])
    else:
        decoded = decode_jwt_unverified(casdoor_jwt)
        payload = dict(decoded.get("payload") or {})
    tid = str(payload.get("tid") or payload.get("tenant") or payload.get("org") or "").strip()
    uid = str(payload.get("uid") or payload.get("name") or payload.get("sub") or "").strip()
    if not tid or not uid:
        raise ValueError("Casdoor token missing tid/tenant and uid/name/sub")
    role = str(payload.get("role") or "user")
    return TenantContext(tenant_id=tid, user_id=uid, role=role)
