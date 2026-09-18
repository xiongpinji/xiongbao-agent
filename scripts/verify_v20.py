# SPDX-License-Identifier: MIT
"""Verify WorkBuddy V20 1:1 parity (stream / timeline / library / team / worktree)."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

WB = ROOT / "octop" / "contrib" / "workbuddy"
CONSOLE = WB / "console"
SHELL = CONSOLE / "shell.html"
PARITY_JS = CONSOLE / "shell_parity.js"


class V20ParityTests(unittest.TestCase):
    def test_shell_v20_ui(self) -> None:
        html = SHELL.read_text(encoding="utf-8")
        self.assertIn("pane-timeline", html)
        self.assertIn("run-events", html)
        self.assertIn("wbStreamDelta", html)
        self.assertIn("shell_parity.js", html)
        js = PARITY_JS.read_text(encoding="utf-8")
        for needle in (
            "btnWorktree",
            "assistant_delta",
            "/api/team/run",
            "/api/library",
            "wizard",
            "lib-tree",
        ):
            self.assertIn(needle, js)

    def test_api_routes(self) -> None:
        src = (WB / "console_server.py").read_text(encoding="utf-8")
        self.assertIn("run-events", src)
        self.assertIn("/api/worktree", src)
        parity = (WB / "console_parity_api.py").read_text(encoding="utf-8")
        self.assertIn("/api/team/run", parity)
        self.assertIn("/api/library/ingest", parity)
        self.assertIn("_channel_wizard", parity)

    def test_stream_deltas_emitted(self) -> None:
        from octop.contrib.workbuddy.console_events import read_events
        from octop.contrib.workbuddy.runtime.task_runner import run_task
        from octop.contrib.workbuddy.security import PolicyStore, SecurityPolicy
        from octop.contrib.workbuddy.task import TaskStore

        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            tasks = base / "tasks"
            goals = base / "goals"
            store = TaskStore(tasks)
            rec = store.create("stream", prompt="写一个 hello.md", mode="craft")
            policy = base / "policy.json"
            PolicyStore(policy).save(SecurityPolicy(default_mode="craft"))
            result = run_task(
                rec.task_id,
                tasks_root=tasks,
                goals_root=goals,
                policy_path=policy,
                dry_run=False,
            )
            self.assertTrue(result.ok)
            rows, _ = read_events(store._dir(rec.task_id), after=0)  # noqa: SLF001
            kinds = [r.get("kind") for r in rows]
            self.assertIn("assistant_delta", kinds)
            self.assertTrue(any(k in {"completed", "failed", "done"} for k in kinds))

    def test_team_dry_and_library(self) -> None:
        from octop.contrib.workbuddy.console_parity_api import (
            _list_team_experts,
            api_get_extra,
            api_post_extra,
        )
        from octop.contrib.workbuddy.tenant import TenantContext

        experts = _list_team_experts(limit=5)
        self.assertTrue(experts, "expert library should resolve")
        ctx = TenantContext(tenant_id="t", user_id="u")
        code, payload = api_get_extra("/api/team", ctx, {})
        self.assertEqual(code, 200)
        self.assertTrue(payload.get("experts"))
        code2, body2 = api_post_extra(
            "/api/team/run",
            {"expert": experts[0]["id"], "query": "你好", "dry_run": True, "max_members": 1},
            ctx,
        )
        self.assertEqual(code2, 200, body2)
        self.assertTrue(body2.get("dry_run"))
        self.assertTrue(body2.get("final_report"))

        with tempfile.TemporaryDirectory() as tmp:
            from octop.contrib.workbuddy import console_parity_api as cpa

            lib_root = Path(tmp) / "library"
            old = cpa._library_root

            def _lib(_ctx):
                return lib_root

            cpa._library_root = _lib  # type: ignore[assignment]
            try:
                code3, body3 = api_post_extra(
                    "/api/library/ingest",
                    {"text": "# hello\nworld", "title": "a.md"},
                    ctx,
                )
                self.assertEqual(code3, 200, body3)
                code4, body4 = api_get_extra("/api/library", ctx, {})
                self.assertEqual(code4, 200)
                self.assertTrue(body4.get("tree") or body4.get("entries"))
            finally:
                cpa._library_root = old  # type: ignore[assignment]

    def test_worktree_dry(self) -> None:
        from octop.contrib.workbuddy import console_parity_api as cpa
        from octop.contrib.workbuddy.console_parity_api import api_post_extra
        from octop.contrib.workbuddy.tenant import TenantContext

        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            repo = base / "repo"
            repo.mkdir()
            (repo / ".git").mkdir()
            ctx = TenantContext(tenant_id="t", user_id="u")
            old = cpa._roots

            class _Fake:
                def __init__(self) -> None:
                    self.root = base / "tenant"
                    self.tasks = self.root / "tasks"

                def ensure(self) -> None:
                    self.root.mkdir(parents=True, exist_ok=True)
                    self.tasks.mkdir(parents=True, exist_ok=True)

            fake = _Fake()
            fake.ensure()

            def _r(_ctx):
                return fake

            cpa._roots = _r  # type: ignore[assignment]
            try:
                code, body = api_post_extra(
                    "/api/worktree",
                    {"repo": str(repo), "title": "wt", "dry_run": True},
                    ctx,
                )
                self.assertEqual(code, 200, body)
                self.assertTrue(body.get("dry_run"))
                self.assertTrue(body.get("task"))
            finally:
                cpa._roots = old  # type: ignore[assignment]


def main() -> int:
    print("=" * 60)
    print("▶ v20 parity unit tests")
    print("=" * 60)
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(V20ParityTests)
    result = unittest.TextTestRunner(verbosity=1).run(suite)
    if not result.wasSuccessful():
        return 1
    print("OK v20 parity unit tests")
    print("\nVERIFY V20 OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
