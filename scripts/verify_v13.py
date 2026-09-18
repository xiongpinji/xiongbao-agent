# SPDX-License-Identifier: MIT
"""Verify V13 upload / rich preview / enterprise / harbor dry-run APIs."""

from __future__ import annotations

import base64
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def _ok(msg: str) -> None:
    print(f"OK {msg}")


class V13Tests(unittest.TestCase):
    def test_upload_and_preview(self) -> None:
        from octop.contrib.workbuddy.console_workspace import (
            build_preview,
            save_upload,
            workspace_payload,
        )

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "task.json").write_text("{}", encoding="utf-8")
            up = save_upload(root, filename="note.md", text="# Hello\n\n**bold**")
            self.assertTrue(up["ok"])
            self.assertTrue((root / "attachments" / "note.md").is_file())
            prev = build_preview(root / "attachments" / "note.md", rel=up["path"])
            self.assertEqual(prev["format"], "markdown")
            html = save_upload(root, filename="page.html", text="<h1>Hi</h1>")
            self.assertTrue(html["ok"])
            prev2 = build_preview(root / "attachments" / "page.html", rel=html["path"])
            self.assertEqual(prev2["format"], "html")
            png = base64.b64encode(
                b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde"
            ).decode()
            img = save_upload(root, filename="dot.png", content_base64=png)
            self.assertTrue(img["ok"])
            prev3 = build_preview(root / "attachments" / "dot.png", rel=img["path"])
            self.assertEqual(prev3["format"], "image")
            self.assertTrue(prev3["content"].startswith("data:image/png;base64,"))
            ws = workspace_payload(root, {"results": [{"kind": "upload", "path": up["path"]}]})
            self.assertTrue(any(f["path"].startswith("attachments/") for f in ws["files"]))

    def test_api_upload_enterprise_harbor(self) -> None:
        from octop.contrib.workbuddy import console_server as cs

        with tempfile.TemporaryDirectory() as td:
            os.environ["WB_MULTI_TENANT"] = "0"
            os.environ["WB_CONSOLE_AUTH"] = "0"
            old = Path.cwd()
            try:
                os.chdir(td)
                Path("artifacts/tasks").mkdir(parents=True)
                code, created = cs.api_post("/api/tasks", {}, {"title": "up", "mode": "craft"}, None)
                self.assertEqual(code, 200)
                tid = created["task"]["task_id"]
                code2, uploaded = cs.api_post(
                    f"/api/tasks/{tid}/upload",
                    {},
                    {"filename": "a.md", "text": "# a"},
                    None,
                )
                self.assertEqual(code2, 200)
                self.assertTrue(uploaded["upload"]["ok"])
                code3, ent = 200, cs.api_payload("/api/enterprise", None)
                self.assertEqual(code3, 200)
                self.assertIn("casdoor", ent)
                self.assertIn("milvus", ent)
                # dry-run may fail without bash; must return structured dict
                code4, dry = cs.api_post("/api/harbor/dry-run", {}, {"timeout": 5}, None)
                self.assertEqual(code4, 200)
                self.assertIn("ok", dry)
            finally:
                os.chdir(old)

    def test_hub_v13(self) -> None:
        from octop.contrib.workbuddy.hub import hub_status

        data = hub_status()
        self.assertGreaterEqual(int(data["v"]), 13)
        apis = data["console"]["apis"]
        self.assertIn("/api/tasks/{id}/upload", apis)
        self.assertIn("/api/enterprise", apis)
        self.assertIn("/api/harbor/dry-run", apis)


def main() -> int:
    print("=" * 60)
    print("▶ v13 unit tests")
    print("=" * 60)
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(V13Tests)
    result = unittest.TextTestRunner(verbosity=1).run(suite)
    if not result.wasSuccessful():
        return 1
    _ok("v13 unit tests")
    print("\nVERIFY V13 OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
