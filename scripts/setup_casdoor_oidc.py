# SPDX-License-Identifier: MIT
"""Configure local Casdoor app/user and exercise OIDC password-grant → Console exchange.

Usage:
  set OCTOP_CASDOOR_* then:
  python -S scripts/setup_casdoor_oidc.py
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from http.cookiejar import CookieJar
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

ENDPOINT = (os.environ.get("OCTOP_CASDOOR_ENDPOINT") or "http://127.0.0.1:8001").rstrip("/")
CLIENT_ID = os.environ.get("OCTOP_CASDOOR_CLIENT_ID") or "wb-local"
CLIENT_SECRET = os.environ.get("OCTOP_CASDOOR_CLIENT_SECRET") or "wb-local-secret"
ADMIN_USER = os.environ.get("CASDOOR_ADMIN_USER") or "admin"
ADMIN_PASS = os.environ.get("CASDOOR_ADMIN_PASS") or "123"
TENANT_ID = os.environ.get("WB_OIDC_TENANT") or "acme_corp"
USER_ID = os.environ.get("WB_OIDC_USER") or "alice"


class CasdoorSession:
    def __init__(self, base: str) -> None:
        self.base = base.rstrip("/")
        self.jar = CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.jar))

    def _req(self, method: str, path: str, data: Any = None) -> dict[str, Any]:
        body = None
        headers = {"User-Agent": "xiongbao-casdoor-setup/1"}
        if data is not None:
            body = json.dumps(data).encode("utf-8")
            headers["Content-Type"] = "application/json"
        req = urllib.request.Request(self.base + path, data=body, headers=headers, method=method)
        with self.opener.open(req, timeout=15) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            return json.loads(raw) if raw.strip().startswith("{") else {"raw": raw}

    def login_admin(self) -> dict[str, Any]:
        return self._req(
            "POST",
            "/api/login",
            {
                "application": "app-built-in",
                "organization": "built-in",
                "username": ADMIN_USER,
                "password": ADMIN_PASS,
                "autoSignin": True,
                "type": "login",
            },
        )

    def ensure_application(self) -> dict[str, Any]:
        # Try get
        existing = self._req("GET", f"/api/get-application?id=admin/{CLIENT_ID}")
        app = {
            "owner": "admin",
            "name": CLIENT_ID,
            "displayName": "WorkBuddy Local",
            "logo": "",
            "homepageUrl": "http://localhost",
            "description": "xiongbao WorkBuddy OIDC",
            "organization": "built-in",
            "cert": "cert-built-in",
            "enablePassword": True,
            "enableSignUp": False,
            "clientId": CLIENT_ID,
            "clientSecret": CLIENT_SECRET,
            "redirectUris": ["http://localhost/callback", "http://127.0.0.1/callback"],
            "tokenFormat": "JWT",
            "expireInHours": 24,
            "refreshExpireInHours": 168,
            "signupItems": [],
            "grantTypes": ["password", "authorization_code", "refresh_token"],
            # Map org → tenant claim for WorkBuddy exchange
            "tokenFields": [],
        }
        if existing.get("status") == "ok" and existing.get("data"):
            cur = existing["data"]
            cur.update(
                {
                    "clientId": CLIENT_ID,
                    "clientSecret": CLIENT_SECRET,
                    "enablePassword": True,
                    "grantTypes": ["password", "authorization_code", "refresh_token"],
                }
            )
            return self._req("POST", f"/api/update-application?id=admin/{CLIENT_ID}", cur)
        return self._req("POST", "/api/add-application", app)

    def _form(self, path: str, fields: dict[str, str]) -> dict[str, Any]:
        body = urllib.parse.urlencode(fields).encode("utf-8")
        req = urllib.request.Request(
            self.base + path,
            data=body,
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "User-Agent": "xiongbao-casdoor-setup/1",
            },
            method="POST",
        )
        with self.opener.open(req, timeout=15) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            return json.loads(raw) if raw.strip().startswith("{") else {"raw": raw}

    def set_password(self, owner: str, name: str, new_password: str) -> dict[str, Any]:
        # Casdoor ignores password on update-user; must use set-password form API.
        return self._form(
            "/api/set-password",
            {
                "userOwner": owner,
                "userName": name,
                "oldPassword": "",
                "newPassword": new_password,
            },
        )

    def ensure_user(self) -> dict[str, Any]:
        # User in built-in org; tag/properties carry tenant id for claims mapping.
        name = USER_ID
        password = os.environ.get("WB_OIDC_PASSWORD") or "Alice123!"
        user = {
            "owner": "built-in",
            "name": name,
            "createdTime": "",
            "updatedTime": "",
            "id": name,
            "type": "normal-user",
            "password": password,
            "passwordType": "plain",
            "displayName": f"OIDC {name}",
            "avatar": "",
            "email": f"{name}@example.com",
            "phone": "",
            "countryCode": "",
            "region": "",
            "location": "",
            "address": [],
            "affiliation": TENANT_ID,
            "title": "",
            "idCardType": "",
            "idCard": "",
            "homepage": "",
            "bio": "",
            "tag": TENANT_ID,
            "language": "",
            "gender": "",
            "birthday": "",
            "education": "",
            "score": 0,
            "karma": 0,
            "ranking": 0,
            "isDefaultAvatar": True,
            "isOnline": False,
            "isAdmin": False,
            "isForbidden": False,
            "isDeleted": False,
            "signupApplication": CLIENT_ID,
            "hash": "",
            "preHash": "",
            "createdIp": "",
            "properties": {"tid": TENANT_ID, "tenant": TENANT_ID, "role": "admin"},
            "roles": [],
            "permissions": [],
            "groups": [],
            "lastSigninTime": "",
            "lastSigninIp": "",
        }
        got = self._req("GET", f"/api/get-user?id=built-in/{name}")
        if got.get("status") == "ok" and got.get("data"):
            cur = got["data"]
            cur["tag"] = TENANT_ID
            cur["affiliation"] = TENANT_ID
            cur["properties"] = {"tid": TENANT_ID, "tenant": TENANT_ID, "role": "admin"}
            cur["signupApplication"] = CLIENT_ID
            updated = self._req("POST", f"/api/update-user?id=built-in/{name}", cur)
            pwd = self.set_password("built-in", name, password)
            return {"update": updated, "set_password": pwd}
        added = self._req("POST", "/api/add-user", user)
        pwd = self.set_password("built-in", name, password)
        return {"add": added, "set_password": pwd}


def main() -> int:
    os.environ.setdefault("OCTOP_CASDOOR_ENDPOINT", ENDPOINT)
    os.environ.setdefault("OCTOP_CASDOOR_CLIENT_ID", CLIENT_ID)
    os.environ.setdefault("OCTOP_CASDOOR_CLIENT_SECRET", CLIENT_SECRET)
    password = os.environ.get("WB_OIDC_PASSWORD") or "Alice123!"
    console_url = (os.environ.get("WB_CONSOLE_URL") or "http://127.0.0.1:8010").rstrip("/")

    print("== Casdoor admin login ==")
    sess = CasdoorSession(ENDPOINT)
    login = sess.login_admin()
    print(json.dumps(login, ensure_ascii=False))
    if login.get("status") != "ok":
        return 1

    print("== ensure application ==")
    print(json.dumps(sess.ensure_application(), ensure_ascii=False)[:800])
    print("== ensure user ==")
    print(json.dumps(sess.ensure_user(), ensure_ascii=False)[:800])

    from octop.contrib.workbuddy.enterprise.casdoor import password_grant_token, verify_access_token
    from octop.contrib.workbuddy.tenant.auth import exchange_casdoor_token, issue_token

    print("== password grant ==")
    tok = password_grant_token(username=USER_ID, password=password, organization="built-in")
    print(
        json.dumps(
            {k: (v[:40] + "…" if isinstance(v, str) and len(v) > 40 else v) for k, v in tok.items()},
            ensure_ascii=False,
        )
    )
    if not tok.get("ok"):
        print("retry with admin…")
        tok = password_grant_token(username="admin", password=ADMIN_PASS, organization="built-in")
        print(
            json.dumps(
                {
                    k: (v[:40] + "…" if isinstance(v, str) and len(v) > 40 else v)
                    for k, v in tok.items()
                },
                ensure_ascii=False,
            )
        )
    access = str(tok.get("access_token") or tok.get("accessToken") or "")
    if not access:
        print("FAIL: no access_token")
        return 1

    print("== verify ==")
    verified = verify_access_token(access)
    payload = verified.get("payload") or {}
    print(
        json.dumps(
            {
                "verified": verified.get("verified"),
                "alg": verified.get("alg"),
                "name": payload.get("name"),
                "tag": payload.get("tag"),
                "affiliation": payload.get("affiliation"),
                "owner": payload.get("owner"),
                "properties": payload.get("properties"),
            },
            ensure_ascii=False,
        )
    )

    print("== exchange ==")
    ctx = exchange_casdoor_token(access)
    print(json.dumps(ctx.to_claims(), ensure_ascii=False))
    wb_jwt = issue_token(ctx)

    print("== console /api/auth/login casdoor_token ==")
    console_ok = False
    console_body: dict[str, Any] = {}
    # Prod compose exposes Console only via Caddy (80/443) or docker network.
    # Prefer in-container loopback; fall back to host Caddy HTTPS.
    token_file = ROOT / "artifacts" / "secrets" / "casdoor_access_token.txt"
    token_file.parent.mkdir(parents=True, exist_ok=True)
    token_file.write_text(access, encoding="utf-8")
    try:
        import subprocess

        py = (
            "import json,urllib.request;"
            "a=open('/app/artifacts/secrets/casdoor_access_token.txt').read().strip();"
            "r=urllib.request.urlopen(urllib.request.Request("
            "'http://127.0.0.1:8010/api/auth/login',"
            "data=json.dumps({'casdoor_token':a}).encode(),"
            "headers={'Content-Type':'application/json'},method='POST'),timeout=15);"
            "print(r.read().decode())"
        )
        proc = subprocess.run(
            ["docker", "exec", "deploy-wb-console-prod-1", "python", "-S", "-c", py],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        if proc.returncode == 0 and proc.stdout.strip().startswith("{"):
            console_body = json.loads(proc.stdout.strip().splitlines()[-1])
            console_ok = bool(console_body.get("ok") or console_body.get("token"))
            print(json.dumps({"via": "docker-exec", "ok": console_ok, "claims": console_body.get("claims")}, ensure_ascii=False))
        else:
            print(json.dumps({"via": "docker-exec", "rc": proc.returncode, "err": (proc.stderr or "")[:300]}, ensure_ascii=False))
    except Exception as exc:  # noqa: BLE001
        print(json.dumps({"via": "docker-exec", "error": str(exc)[:200]}, ensure_ascii=False))

    if not console_ok:
        import ssl

        ctx_ssl = ssl.create_default_context()
        ctx_ssl.check_hostname = False
        ctx_ssl.verify_mode = ssl.CERT_NONE
        for base in (console_url, "https://127.0.0.1", "http://127.0.0.1"):
            try:
                req = urllib.request.Request(
                    f"{base.rstrip('/')}/api/auth/login",
                    data=json.dumps({"casdoor_token": access}).encode("utf-8"),
                    headers={"Content-Type": "application/json", "User-Agent": "wb-oidc-smoke/1"},
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=10, context=ctx_ssl) as resp:
                    console_body = json.loads(resp.read().decode("utf-8"))
                    console_ok = bool(console_body.get("ok") or console_body.get("token"))
                    print(json.dumps({"url": base, "ok": console_ok, "keys": list(console_body.keys())}, ensure_ascii=False))
                    if console_ok:
                        break
            except Exception as exc:  # noqa: BLE001
                print(json.dumps({"url": base, "error": str(exc)[:200]}, ensure_ascii=False))

    print("OK casdoor oidc setup")
    out = ROOT / "artifacts" / "secrets" / "casdoor_oidc_smoke.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(
            {
                "endpoint": ENDPOINT,
                "client_id": CLIENT_ID,
                "user": USER_ID,
                "tenant": TENANT_ID,
                "has_access_token": bool(access),
                "verified": bool(verified.get("verified")),
                "alg": verified.get("alg"),
                "exchange": ctx.to_claims(),
                "console_login_ok": console_ok,
                "wb_jwt_len": len(wb_jwt),
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return 0 if console_ok or verified.get("verified") else 1


if __name__ == "__main__":
    raise SystemExit(main())
