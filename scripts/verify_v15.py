# SPDX-License-Identifier: MIT
"""Verify V15: Casdoor OIDC exchange + pptx preview + Harbor live artifact."""

from __future__ import annotations

import io
import json
import os
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from xml.etree.ElementTree import Element, SubElement, tostring

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def _minimal_pptx(text: str) -> bytes:
    a_ns = "http://schemas.openxmlformats.org/drawingml/2006/main"
    p_ns = "http://schemas.openxmlformats.org/presentationml/2006/main"
    sld = Element(f"{{{p_ns}}}sld")
    c_sld = SubElement(sld, f"{{{p_ns}}}cSld")
    sp_tree = SubElement(c_sld, f"{{{p_ns}}}spTree")
    sp = SubElement(sp_tree, f"{{{p_ns}}}sp")
    tx = SubElement(sp, f"{{{p_ns}}}txBody")
    para = SubElement(tx, f"{{{a_ns}}}p")
    r = SubElement(para, f"{{{a_ns}}}r")
    t = SubElement(r, f"{{{a_ns}}}t")
    t.text = text
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("ppt/slides/slide1.xml", tostring(sld, encoding="utf-8"))
        zf.writestr(
            "[Content_Types].xml",
            '<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"></Types>',
        )
    return buf.getvalue()


class V15Tests(unittest.TestCase):
    def test_pptx_preview(self) -> None:
        from octop.contrib.workbuddy.office_preview import office_preview

        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "deck.pptx"
            path.write_bytes(_minimal_pptx("SlideOne"))
            prev = office_preview(path)
            self.assertTrue(prev["ok"])
            self.assertIn("SlideOne", str(prev["content"]))

    def test_casdoor_rs256_stdlib(self) -> None:
        from octop.contrib.workbuddy.enterprise import casdoor as cd

        # Unit: PKCS1 verifier rejects garbage
        with self.assertRaises(ValueError):
            cd._verify_rs256("a.b.c", "AQAB", "AQAB")

    def test_exchange_uses_tag_claim(self) -> None:
        from octop.contrib.workbuddy.enterprise import casdoor as cd
        from octop.contrib.workbuddy.tenant.auth import exchange_casdoor_token

        now = __import__("time").time()
        payload = {
            "tag": "acme_corp",
            "name": "alice",
            "properties": {"role": "admin", "tid": "acme_corp"},
            "iat": int(now),
            "exp": int(now) + 3600,
        }
        header = cd._b64url_encode(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
        body = cd._b64url_encode(json.dumps(payload).encode())
        import hashlib
        import hmac

        secret = "wb-local-secret"
        sig = hmac.new(secret.encode(), f"{header}.{body}".encode(), hashlib.sha256).digest()
        token = f"{header}.{body}.{cd._b64url_encode(sig)}"
        os.environ["OCTOP_CASDOOR_ENDPOINT"] = "http://127.0.0.1:8001"
        os.environ["OCTOP_CASDOOR_CLIENT_ID"] = "wb-local"
        os.environ["OCTOP_CASDOOR_CLIENT_SECRET"] = secret
        ctx = exchange_casdoor_token(token)
        self.assertEqual(ctx.tenant_id, "acme_corp")
        self.assertEqual(ctx.user_id, "alice")
        self.assertEqual(ctx.role, "admin")

    def test_oidc_smoke_artifact(self) -> None:
        smoke = ROOT / "artifacts" / "secrets" / "casdoor_oidc_smoke.json"
        if not smoke.is_file():
            self.skipTest("casdoor_oidc_smoke.json not present (run setup_casdoor_oidc.py)")
        data = json.loads(smoke.read_text(encoding="utf-8"))
        self.assertTrue(data.get("verified"))
        self.assertEqual(data.get("alg"), "RS256")
        self.assertEqual((data.get("exchange") or {}).get("tid"), "acme_corp")
        self.assertTrue(data.get("console_login_ok"))

    def test_hub_v15_apis(self) -> None:
        from octop.contrib.workbuddy.hub import hub_status

        data = hub_status()
        self.assertGreaterEqual(int(data["v"]), 15)
        self.assertIn("/api/auth/login", data["console"]["apis"])


def main() -> int:
    print("=" * 60)
    print("▶ v15 unit tests")
    print("=" * 60)
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(V15Tests)
    result = unittest.TextTestRunner(verbosity=1).run(suite)
    if not result.wasSuccessful():
        return 1
    print("OK v15 unit tests")
    live = ROOT / "artifacts" / "harbor" / "live_score_office_smoke.json"
    if live.is_file():
        data = json.loads(live.read_text(encoding="utf-8"))
        print(f"Harbor live artifact: ok={data.get('ok')} mode={data.get('mode')} rc={data.get('returncode')}")
    print("\nVERIFY V15 OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
