# SPDX-License-Identifier: MIT
"""Verify V12 user shell + task APIs."""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("PYTHONPATH", str(ROOT))


def _ok(msg: str) -> None:
    print(f"OK {msg}")


class V12ShellTests(unittest.TestCase):
    def test_task_store_pin_search(self) -> None:
        from octop.contrib.workbuddy.task import TaskStore

        with tempfile.TemporaryDirectory() as td:
            store = TaskStore(td)
            a = store.create(title="alpha report", prompt="do a")
            b = store.create(title="beta plan", prompt="do b")
            store.update(a.task_id, meta_patch={"pinned": True})
            store.update(b.task_id, meta_patch={"archived": True})
            listed = store.list_tasks(query="alpha")
            self.assertEqual(len(listed), 1)
            self.assertEqual(listed[0].task_id, a.task_id)
            self.assertTrue(listed[0].meta.get("pinned"))
            archived = store.list_tasks(include_archived=True, query="beta")
            self.assertEqual(len(archived), 1)

    def test_workspace_payload(self) -> None:
        from octop.contrib.workbuddy.console_workspace import workspace_payload
        from octop.contrib.workbuddy.task import TaskStore

        with tempfile.TemporaryDirectory() as td:
            store = TaskStore(td)
            rec = store.create(title="ws", prompt="hello")
            d = Path(td) / rec.task_id
            (d / "note.md").write_text("# hi\n", encoding="utf-8")
            store.add_result(rec.task_id, {"kind": "dry_run_plan", "steps": []})
            rec2 = store.get(rec.task_id)
            payload = workspace_payload(d, rec2.to_dict())
            self.assertTrue(payload["ok"])
            self.assertTrue(any(f["path"] == "note.md" for f in payload["files"]))
            self.assertTrue(payload["preview"]["ok"])

    def test_api_create_message_workspace(self) -> None:
        from octop.contrib.workbuddy import console_server as cs

        with tempfile.TemporaryDirectory() as td:
            os.environ["WB_MULTI_TENANT"] = "0"
            os.environ["WB_CONSOLE_AUTH"] = "0"
            tasks = Path(td) / "tasks"
            # monkeypatch tasks root via cwd-relative path used when ctx is None
            old = Path.cwd()
            try:
                os.chdir(td)
                Path("artifacts/tasks").mkdir(parents=True, exist_ok=True)
                code, created = cs.api_post("/api/tasks", {}, {"title": "v12", "mode": "ask", "prompt": "hi"}, None)
                self.assertEqual(code, 200)
                tid = created["task"]["task_id"]
                code2, messaged = cs.api_post(
                    f"/api/tasks/{tid}/messages",
                    {},
                    {"content": "follow up", "run": True, "dry": True},
                    None,
                )
                self.assertEqual(code2, 200)
                self.assertGreaterEqual(len(messaged["task"]["messages"]), 2)
                code3, detail = cs.api_get_task_path(f"/api/tasks/{tid}", None, {})
                self.assertEqual(code3, 200)
                code4, ws = cs.api_get_task_path(f"/api/tasks/{tid}/workspace", None, {})
                self.assertEqual(code4, 200)
                self.assertIn("artifacts", ws)
            finally:
                os.chdir(old)

    def test_shell_and_ops_exist(self) -> None:
        console = ROOT / "octop" / "contrib" / "workbuddy" / "console"
        self.assertTrue((console / "shell.html").is_file())
        self.assertTrue((console / "ops.html").is_file())

    def test_hub_v12(self) -> None:
        from octop.contrib.workbuddy.hub import hub_status

        data = hub_status()
        self.assertGreaterEqual(int(data["v"]), 12)
        apis = data["console"]["apis"]
        self.assertIn("/api/tasks/{id}/workspace", apis)
        self.assertIn("/api/skills/install", apis)


def main() -> int:
    print("=" * 60)
    print("▶ v12 unit tests")
    print("=" * 60)
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(V12ShellTests)
    result = unittest.TextTestRunner(verbosity=1).run(suite)
    if not result.wasSuccessful():
        return 1
    _ok("v12 unit tests")

    print("=" * 60)
    print("▶ docs")
    print("=" * 60)
    for rel in (
        "TASKBOARD.md",
        "deploy/enterprise/WORKBUDDY_PARITY_AUDIT.md",
        "octop/contrib/workbuddy/console/shell.html",
    ):
        p = ROOT / rel
        if not p.is_file():
            print(f"MISSING {rel}")
            return 1
        _ok(rel)

    print("\nVERIFY V12 OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
