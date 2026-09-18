# SPDX-License-Identifier: MIT
"""Verify V14 office preview / enterprise probe / harbor score."""

from __future__ import annotations

import io
import os
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from xml.etree.ElementTree import Element, SubElement, tostring

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def _minimal_docx(text: str) -> bytes:
    document = Element(
        "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}document"
    )
    body = SubElement(document, "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}body")
    p = SubElement(body, "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}p")
    r = SubElement(p, "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}r")
    t = SubElement(r, "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t")
    t.text = text
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("word/document.xml", tostring(document, encoding="utf-8"))
        zf.writestr(
            "[Content_Types].xml",
            '<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"></Types>',
        )
    return buf.getvalue()


class V14Tests(unittest.TestCase):
    def test_docx_preview(self) -> None:
        from octop.contrib.workbuddy.office_preview import office_preview

        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "a.docx"
            path.write_bytes(_minimal_docx("HelloDocx"))
            prev = office_preview(path)
            self.assertTrue(prev["ok"])
            self.assertIn("HelloDocx", str(prev["content"]))

    def test_harbor_score_dry(self) -> None:
        from octop.contrib.workbuddy import console_server as cs

        code, payload = cs.api_post("/api/harbor/score", {}, {"live": False}, None)
        self.assertEqual(code, 200)
        self.assertTrue(payload.get("ok"))
        self.assertEqual(payload.get("mode"), "dry_run")

    def test_enterprise_payload(self) -> None:
        from octop.contrib.workbuddy.enterprise.probe import enterprise_probe

        data = enterprise_probe()
        self.assertIn("casdoor", data)
        self.assertIn("milvus", data)
        self.assertTrue(data["casdoor"]["wired"])

    def test_hub_v14(self) -> None:
        from octop.contrib.workbuddy.hub import hub_status

        data = hub_status()
        self.assertGreaterEqual(int(data["v"]), 14)
        self.assertIn("/api/harbor/score", data["console"]["apis"])


def main() -> int:
    print("=" * 60)
    print("▶ v14 unit tests")
    print("=" * 60)
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(V14Tests)
    result = unittest.TextTestRunner(verbosity=1).run(suite)
    if not result.wasSuccessful():
        return 1
    print("OK v14 unit tests")
    print("\nVERIFY V14 OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
