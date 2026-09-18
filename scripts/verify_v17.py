# SPDX-License-Identifier: MIT
"""Verify V17 UX quality lift — static shell + humanize + APIs."""

from __future__ import annotations

import re
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

CONSOLE = ROOT / "octop" / "contrib" / "workbuddy" / "console"
SHELL = CONSOLE / "shell.html"
TOKENS = CONSOLE / "tokens.css"
SHELL_CSS = CONSOLE / "shell.css"


class V17StaticTests(unittest.TestCase):
    def test_css_extracted(self) -> None:
        self.assertTrue(TOKENS.is_file(), TOKENS)
        self.assertTrue(SHELL_CSS.is_file(), SHELL_CSS)
        tokens = TOKENS.read_text(encoding="utf-8")
        self.assertIn("--accent:", tokens)
        self.assertIn("--sidebar-w:", tokens)
        css = SHELL_CSS.read_text(encoding="utf-8")
        self.assertIn(".more-menu", css)
        self.assertIn(".toast", css)
        self.assertIn(".login-brand", css)
        self.assertIn(".mobile-tabs", css)

    def test_shell_landmarks_and_copy(self) -> None:
        html = SHELL.read_text(encoding="utf-8")
        self.assertIn('href="/console/tokens.css"', html)
        self.assertIn('href="/console/shell.css"', html)
        self.assertIn("<header", html)
        self.assertIn("<main", html)
        self.assertIn("<nav", html)
        self.assertIn('id="btnMore"', html)
        self.assertIn("仅演练", html)
        self.assertIn("Casdoor 换发", html)
        self.assertIn("新建第一个任务", html)
        self.assertIn("mobileTabs", html)
        self.assertIn("ROLE_LABEL", html)
        self.assertIn("humanizeContent", html)
        self.assertIn('id="modelChip"', html)
        self.assertIn('id="dryRun"', html)
        # dry-run default unchecked
        self.assertNotRegex(html, re.compile(r'id="dryRun"[^>]*checked'))
        # ops demoted
        self.assertIn("设置", html)
        self.assertIn("/ops.html", html)

    def test_no_inline_style_block_for_layout(self) -> None:
        html = SHELL.read_text(encoding="utf-8")
        # layout tokens live in external CSS
        self.assertNotIn(":root {\n      --bg:", html)


class V17HumanizeTests(unittest.TestCase):
    def test_dry_run_chinese_message(self) -> None:
        from octop.contrib.workbuddy.runtime.task_runner import run_task
        from octop.contrib.workbuddy.security import PolicyStore, SecurityPolicy
        from octop.contrib.workbuddy.task import TaskStore

        with tempfile.TemporaryDirectory() as tmp:
            tasks = Path(tmp) / "tasks"
            store = TaskStore(tasks)
            rec = store.create("weekly", prompt="写 weekly.md", mode="craft")
            policy = Path(tmp) / "policy.json"
            PolicyStore(policy).save(SecurityPolicy(default_mode="craft"))
            result = run_task(
                rec.task_id,
                tasks_root=tasks,
                policy_path=policy,
                kb_root=None,
                dry_run=True,
            )
            self.assertTrue(result.ok)
            msgs = store.get(rec.task_id).messages
            texts = " ".join(m.content for m in msgs)
            self.assertIn("演练", texts)
            self.assertNotIn("[dry-run]", texts)
            self.assertNotIn("planned", texts.lower())

    def test_task_delete(self) -> None:
        from octop.contrib.workbuddy.task import TaskStore

        with tempfile.TemporaryDirectory() as tmp:
            store = TaskStore(Path(tmp))
            rec = store.create("to-delete")
            self.assertTrue(store.delete(rec.task_id))
            with self.assertRaises(FileNotFoundError):
                store.get(rec.task_id)

    def test_resolve_download(self) -> None:
        from octop.contrib.workbuddy.console_workspace import resolve_download

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            f = root / "attachments" / "a.txt"
            f.parent.mkdir(parents=True)
            f.write_text("hi", encoding="utf-8")
            path, err = resolve_download(root, "attachments/a.txt")
            self.assertEqual(err, "")
            self.assertEqual(path, f.resolve())
            bad, err2 = resolve_download(root, "../x")
            self.assertIsNone(bad)
            self.assertTrue(err2)


class V17ApiSmokeTests(unittest.TestCase):
    def test_health_payload_shape(self) -> None:
        from octop.contrib.workbuddy.console_server import api_payload

        data = api_payload("/api/health", None)
        self.assertTrue(data["ok"])
        self.assertEqual(data["v"], 17)
        self.assertIn("model", data)
        self.assertIn("auth_required", data)

    def test_messages_default_live_flag(self) -> None:
        src = (ROOT / "octop" / "contrib" / "workbuddy" / "console_server.py").read_text(encoding="utf-8")
        self.assertIn("live by default", src)
        self.assertIn('_as_bool(body.get("dry"), default=False)', src)

    def test_hub_v17(self) -> None:
        from octop.contrib.workbuddy.hub import hub_status

        self.assertEqual(hub_status()["v"], 17)


def main() -> int:
    print("=" * 60)
    print("▶ v17 unit tests")
    print("=" * 60)
    loader = unittest.defaultTestLoader
    suite = unittest.TestSuite()
    suite.addTests(loader.loadTestsFromTestCase(V17StaticTests))
    suite.addTests(loader.loadTestsFromTestCase(V17HumanizeTests))
    suite.addTests(loader.loadTestsFromTestCase(V17ApiSmokeTests))
    result = unittest.TextTestRunner(verbosity=1).run(suite)
    if not result.wasSuccessful():
        return 1
    print("OK v17 unit tests")
    print("\nVERIFY V17 OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
