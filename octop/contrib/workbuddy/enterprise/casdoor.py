# SPDX-License-Identifier: MIT
"""Casdoor JWT verification client (stdlib, env-gated).

Supports HS256 (client secret) and RS256 (JWKS from Casdoor discovery).
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


def _int_from_bytes(data: bytes) -> int:
    return int.from_bytes(data, "big")


# ASN.1 DigestInfo prefix for SHA-256 (RFC 8017)
_SHA256_DIGESTINFO = bytes.fromhex("3031300d060960864801650304020105000420")


def _verify_rs256(token: str, n_b64: str, e_b64: str) -> dict[str, Any]:
    """Verify RS256 JWT using JWK n/e (stdlib PKCS#1 v1.5)."""
    parts = token.split(".")
    if len(parts) != 3:
        raise ValueError("malformed JWT")
    n = _int_from_bytes(_b64url_decode(n_b64))
    e = _int_from_bytes(_b64url_decode(e_b64))
    sig = _b64url_decode(parts[2])
    k = (n.bit_length() + 7) // 8
    if len(sig) != k:
        # allow short signatures by left-padding
        if len(sig) > k:
            raise ValueError("RSA signature length mismatch")
        sig = b"\x00" * (k - len(sig)) + sig
    em = pow(_int_from_bytes(sig), e, n).to_bytes(k, "big")
    digest = hashlib.sha256(f"{parts[0]}.{parts[1]}".encode("ascii")).digest()
    expected_tail = _SHA256_DIGESTINFO + digest
    # EMSA-PKCS1-v1_5: 0x00 || 0x01 || PS || 0x00 || T
    if len(em) < len(expected_tail) + 3 or em[0] != 0x00 or em[1] != 0x01:
        raise ValueError("invalid RSA PKCS1 padding")
    if not em.endswith(expected_tail):
        raise ValueError("invalid RS256 signature")
    sep = em.index(b"\x00", 2)
    if sep < 10 or em[sep + 1 :] != expected_tail:
        raise ValueError("invalid RSA DigestInfo")
    if any(b != 0xFF for b in em[2:sep]):
        raise ValueError("invalid RSA PS")
    payload = json.loads(_b64url_decode(parts[1]))
    now = int(time.time())
    exp = payload.get("exp")
    if isinstance(exp, (int, float)) and now > int(exp):
        raise ValueError("JWT expired")
    return payload


def fetch_jwks() -> dict[str, Any]:
    endpoint = _env("OCTOP_CASDOOR_ENDPOINT").rstrip("/")
    url = f"{endpoint}/.well-known/jwks"
    req = urllib.request.Request(url, method="GET")
    req.add_header("User-Agent", "xiongbao-casdoor/1")
    with urllib.request.urlopen(req, timeout=5.0) as resp:
        return json.loads(resp.read().decode("utf-8"))


def verify_access_token(token: str) -> dict[str, Any]:
    """Verify Casdoor token: try HS256 client secret, then RS256 JWKS."""
    if not casdoor_configured():
        raise RuntimeError("Casdoor not configured (set OCTOP_CASDOOR_ENDPOINT + CLIENT_ID)")
    header = decode_jwt_unverified(token)["header"]
    alg = str(header.get("alg") or "HS256")
    secret = _env("OCTOP_CASDOOR_CLIENT_SECRET")
    errors: list[str] = []

    if alg.startswith("HS") and secret:
        try:
            payload = verify_hs256(token, secret)
            return {"verified": True, "alg": "HS256", "payload": payload}
        except ValueError as exc:
            errors.append(f"HS256: {exc}")

    if alg.startswith("RS") or not secret:
        try:
            jwks = fetch_jwks()
            kid = header.get("kid")
            keys = list(jwks.get("keys") or [])
            chosen = None
            for k in keys:
                if kid and k.get("kid") == kid:
                    chosen = k
                    break
            if chosen is None and keys:
                chosen = keys[0]
            if not chosen or not chosen.get("n") or not chosen.get("e"):
                raise ValueError("no usable JWK")
            payload = _verify_rs256(token, str(chosen["n"]), str(chosen["e"]))
            return {"verified": True, "alg": "RS256", "payload": payload, "kid": chosen.get("kid")}
        except Exception as exc:  # noqa: BLE001
            errors.append(f"RS256: {exc}")

    if not secret and alg.startswith("HS"):
        decoded = decode_jwt_unverified(token)
        return {
            "verified": False,
            "reason": "OCTOP_CASDOOR_CLIENT_SECRET not set — payload decoded only",
            **decoded,
        }
    raise ValueError("; ".join(errors) or "token verification failed")


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


def fetch_userinfo(access_token: str) -> dict[str, Any]:
    endpoint = _env("OCTOP_CASDOOR_ENDPOINT").rstrip("/")
    if not endpoint:
        return {"ok": False, "error": "endpoint unset"}
    url = f"{endpoint}/api/userinfo"
    req = urllib.request.Request(url, method="GET")
    req.add_header("Authorization", f"Bearer {access_token}")
    req.add_header("User-Agent", "xiongbao-casdoor/1")
    try:
        with urllib.request.urlopen(req, timeout=8.0) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return {"ok": True, "data": data}
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")[:400]
        return {"ok": False, "error": f"HTTP {exc.code}", "body": body}
    except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
        return {"ok": False, "error": str(exc)[:300]}


def password_grant_token(
    *,
    username: str,
    password: str,
    organization: str = "built-in",
) -> dict[str, Any]:
    """Resource-owner password grant against Casdoor token endpoint."""
    endpoint = _env("OCTOP_CASDOOR_ENDPOINT").rstrip("/")
    client_id = _env("OCTOP_CASDOOR_CLIENT_ID")
    client_secret = _env("OCTOP_CASDOOR_CLIENT_SECRET")
    if not endpoint or not client_id:
        return {"ok": False, "error": "Casdoor not configured"}
    url = f"{endpoint}/api/login/oauth/access_token"
    # Prefer bare username (Casdoor app already binds organization); try org/name next.
    candidates = [username]
    if "/" not in username and organization:
        candidates.append(f"{organization}/{username}")
    last: dict[str, Any] = {"ok": False, "error": "no attempt"}
    for user in candidates:
        form = urllib.parse.urlencode(
            {
                "grant_type": "password",
                "client_id": client_id,
                "client_secret": client_secret,
                "username": user,
                "password": password,
            }
        ).encode("utf-8")
        req = urllib.request.Request(url, data=form, method="POST")
        req.add_header("Content-Type", "application/x-www-form-urlencoded")
        req.add_header("User-Agent", "xiongbao-casdoor/1")
        try:
            with urllib.request.urlopen(req, timeout=10.0) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return {"ok": True, "username_used": user, **data}
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")[:500]
            last = {"ok": False, "error": f"HTTP {exc.code}", "body": body, "username_used": user}
        except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
            last = {"ok": False, "error": str(exc)[:300], "username_used": user}
    return last
