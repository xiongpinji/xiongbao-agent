# SPDX-License-Identifier: MIT
"""V10 runtime wiring unit tests (stdlib only)."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from http.client import HTTPConnection
from pathlib import Path
from threading import Thread

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from octop.contrib.workbuddy.channel_bridge import ChannelBridge
from octop.contrib.workbuddy.connectors.china_im import InboxStore
from octop.contrib.workbuddy.console_server import api_payload, api_post
from octop.contrib.workbuddy.cowrite import CowriteStore
from octop.contrib.workbuddy.hub import hub_status
from octop.contrib.workbuddy.knowledge import LocalKnowledgeBase
from octop.contrib.workbuddy.models_profile import ModelProfile, ModelProfileStore
from octop.contrib.workbuddy.runtime import (
    apply_profile_env,
    check_run_allowed,
    create_task_with_worktree,
    export_parity_bundle,
    import_parity_bundle,
    kb_prompt_prefix,
    publish_cowrite_to_library,
    register_installed_skill,
    run_task,
)
from octop.contrib.workbuddy.runtime.inbox_poll import InboxPoller
from octop.contrib.workbuddy.security import PolicyStore, SecurityPolicy
from octop.contrib.workbuddy.task import TaskStore


class TestV101TaskRunner(unittest.TestCase):
    def test_dry_run_plan(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tasks = Path(tmp) / "tasks"
            store = TaskStore(tasks)
            rec = store.create("write weekly", prompt="写入 weekly.md", mode="craft")
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
            self.assertTrue(result.dry_run)
            self.assertEqual(result.status, "waiting")
            self.assertGreater(result.detail.get("plan_steps", 0), 0)


class TestV102PolicyGate(unittest.TestCase):
    def test_ask_blocks_write(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "p.json"
            PolicyStore(path).save(SecurityPolicy(default_mode="ask"))
            d = check_run_allowed(mode="ask", policy_path=path, needs_write=True)
            self.assertFalse(d.allowed)
            d2 = check_run_allowed(mode="craft", policy_path=path, needs_write=True)
            self.assertTrue(d2.allowed)


class TestV103ProfileEnv(unittest.TestCase):
    def test_apply(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "profiles.json"
            store = ModelProfileStore(path)
            store.upsert(
                ModelProfile(
                    profile_id="local",
                    base_url="http://127.0.0.1:11434/v1",
                    model="qwen2.5:3b",
                )
            )
            store.set_active("local")
            env: dict[str, str] = {}
            out = apply_profile_env(path=path, environ=env)
            self.assertTrue(out["applied"])
            self.assertEqual(env["WB_LLM_MODEL"], "qwen2.5:3b")


class TestV104InboxPoll(unittest.TestCase):
    def test_cursor_once(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            inbox_path = Path(tmp) / "inbox.jsonl"
            tasks = Path(tmp) / "tasks"
            inbox = InboxStore(inbox_path)
            inbox.append("wechat", {"text": "/task hello from im", "sender": "u1"})
            store = TaskStore(tasks)
            bridge = ChannelBridge(store, allow=True)
            poller = InboxPoller(inbox, bridge, cursor_path=Path(tmp) / "c.cur")
            r1 = poller.poll()
            self.assertEqual(r1["processed"], 1)
            r2 = poller.poll()
            self.assertEqual(r2["processed"], 0)
            self.assertEqual(len(store.list_tasks()), 1)


class TestV105SkillRegister(unittest.TestCase):
    def test_register_local(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "demo-skill"
            src.mkdir()
            (src / "SKILL.md").write_text(
                "---\nname: demo-skill\ndescription: test\n---\n# Demo\n",
                encoding="utf-8",
            )
            dest = Path(tmp) / "installed"
            out = register_installed_skill(src, dest_root=dest, force=True)
            self.assertTrue(out["registered"])
            self.assertTrue(out["visible_in_catalog"])
            self.assertTrue((dest / "installed.json").is_file())


class TestV106KbContext(unittest.TestCase):
    def test_prefix(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            kb = LocalKnowledgeBase(tmp)
            f = Path(tmp) / "note.md"
            f.write_text("周报模板包含进度与风险", encoding="utf-8")
            kb.ingest_file(f)
            prefix = kb_prompt_prefix(tmp, "周报", limit=2)
            self.assertIn("Knowledge recall", prefix)


class TestV107Bundle(unittest.TestCase):
    def test_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            art = Path(tmp) / "artifacts"
            (art / "tasks" / "t1").mkdir(parents=True)
            (art / "tasks" / "t1" / "task.json").write_text("{}", encoding="utf-8")
            (art / "knowledge").mkdir()
            (art / "knowledge" / "x.txt").write_text("hi", encoding="utf-8")
            archive = Path(tmp) / "bundle.zip"
            exp = export_parity_bundle(art, archive)
            self.assertIn("tasks", exp["roots"])
            dest = Path(tmp) / "restored"
            imp = import_parity_bundle(archive, dest)
            self.assertIn("tasks", imp["restored"])
            self.assertTrue((dest / "tasks" / "t1" / "task.json").is_file())


class TestV108WorktreeBind(unittest.TestCase):
    def test_dry_meta(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = create_task_with_worktree(
                "wt-demo",
                tasks_root=Path(tmp) / "tasks",
                repo=tmp,
                worktrees_dir=Path(tmp) / "wt",
                with_worktree=True,
                dry_run=True,
                prompt="hi",
            )
            self.assertIn("worktree", out["task"]["meta"])
            self.assertEqual(out["worktree"]["task_id"], out["task"]["task_id"])


class TestV109CowritePublish(unittest.TestCase):
    def test_publish(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cw = CowriteStore(Path(tmp) / "cw")
            sess = cw.start("doc", seed="hello")
            cw.append(sess.session_id, "human", "world")
            out = publish_cowrite_to_library(
                sess.session_id,
                cowrite_root=Path(tmp) / "cw",
                library_root=Path(tmp) / "lib",
            )
            self.assertTrue(out["ok"])
            self.assertTrue(Path(out["publish"]).is_file())


class TestV1010HubConsole(unittest.TestCase):
    def test_hub_v10(self) -> None:
        data = hub_status()
        self.assertEqual(data["v"], 10)
        self.assertIn("runtime", data)

    def test_api_runtime(self) -> None:
        payload = api_payload("/api/runtime")
        self.assertTrue(payload.get("ok"))
        self.assertIn("runtime", payload)

    def test_post_run_missing(self) -> None:
        r = api_post("/api/runtime/run-task", {})
        self.assertFalse(r.get("ok"))


def main() -> int:
    suite = unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__])
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    print(f"\nV10 TESTS: {result.testsRun} run, failures={len(result.failures)} errors={len(result.errors)}")
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
