# SPDX-License-Identifier: MIT
"""Verify WorkBuddy parity gaps (SSE / members / shell panels)."""

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


class ParityGapTests(unittest.TestCase):
    def test_shell_wires_parity(self) -> None:
        html = SHELL.read_text(encoding="utf-8")
        self.assertIn("shell_parity.js", html)
        self.assertIn("wbApi", html)
        self.assertIn("wbParity", html)
        self.assertIn("stream:", html)
        self.assertIn("consumeEvents", html)
        self.assertIn("/members", html)
        self.assertIn("btnAddMember", html)

    def test_parity_js_panels(self) -> None:
        js = PARITY_JS.read_text(encoding="utf-8")
        for needle in (
            "btnKnowledge",
            "btnCowrite",
            "btnMemory",
            "btnModels",
            "btnChannels",
            "btnTeam",
            "runProgress",
            "consumeEvents",
            "/api/tasks/",
            "/events",
        ):
            self.assertIn(needle, js)

    def test_console_server_sse_and_extras(self) -> None:
        src = (WB / "console_server.py").read_text(encoding="utf-8")
        self.assertIn("iter_sse_frames", src)
        self.assertIn("streaming", src)
        self.assertIn("api_post_extra", src)
        self.assertIn("text/event-stream", src)

    def test_events_and_members_unit(self) -> None:
        from octop.contrib.workbuddy.console_events import append_event, make_emitter, read_events
        from octop.contrib.workbuddy.console_parity_api import (
            normalize_members,
            require_role,
            save_project_meta,
        )
        from octop.contrib.workbuddy.project import ProjectSpace

        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            task_dir = base / "t1"
            task_dir.mkdir()
            emit = make_emitter(task_dir)
            emit({"kind": "running", "message": "go"})
            append_event(task_dir, {"kind": "done", "terminal": True})
            rows, cur = read_events(task_dir, after=0)
            self.assertGreaterEqual(len(rows), 2)
            self.assertEqual(rows[-1]["kind"], "done")
            self.assertGreater(cur, 0)

            space = ProjectSpace(base / "projects")
            meta = space.create(
                "p1",
                name="P1",
                members=[{"user_id": "alice", "role": "owner"}],
            )
            meta.members = normalize_members(list(meta.members or []))
            save_project_meta(space, meta)
            ok, role = require_role(space, "p1", "alice", "owner")
            self.assertTrue(ok)
            self.assertEqual(role, "owner")
            ok2, _ = require_role(space, "p1", "bob", "viewer")
            self.assertFalse(ok2)

    def test_http_parity_routes(self) -> None:
        from octop.contrib.workbuddy import console_parity_api as cpa
        from octop.contrib.workbuddy.console_parity_api import (
            api_get_extra,
            api_post_extra,
            normalize_members,
            save_project_meta,
        )
        from octop.contrib.workbuddy.console_server import _Handler
        from octop.contrib.workbuddy.project import ProjectSpace
        from octop.contrib.workbuddy.tenant import TenantContext, issue_token

        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            ctx = TenantContext(tenant_id="t-demo", user_id="u-demo")
            code, payload = api_get_extra("/api/team", ctx, {})
            self.assertEqual(code, 200)
            self.assertTrue(payload.get("ok"))
            code2, payload2 = api_get_extra("/api/channels", ctx, {})
            self.assertEqual(code2, 200)
            self.assertTrue(payload2.get("ok"))

            projects = base / "projects"
            space = ProjectSpace(projects)
            space.create("memdemo", name="Mem", members=[{"user_id": "u-demo", "role": "owner"}])
            meta = space.load("memdemo")
            meta.members = normalize_members(list(meta.members or []))
            save_project_meta(space, meta)

            old = cpa._projects_root

            def _root(_ctx):
                return projects

            cpa._projects_root = _root  # type: ignore[assignment]
            try:
                code3, body3 = api_post_extra(
                    "/api/projects/memdemo/members",
                    {"user_id": "bob", "role": "editor", "action": "upsert"},
                    ctx,
                )
                self.assertEqual(code3, 200, body3)
                self.assertTrue(any(m["user_id"] == "bob" for m in body3.get("members") or []))
            finally:
                cpa._projects_root = old  # type: ignore[assignment]

            self.assertTrue(callable(_Handler))
            self.assertTrue(callable(issue_token))


def main() -> int:
    print("=" * 60)
    print("▶ parity-gaps unit tests")
    print("=" * 60)
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(ParityGapTests)
    result = unittest.TextTestRunner(verbosity=1).run(suite)
    if not result.wasSuccessful():
        return 1
    print("OK parity-gaps unit tests")
    print("\nVERIFY PARITY GAPS OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
