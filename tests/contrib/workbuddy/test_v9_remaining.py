# SPDX-License-Identifier: MIT
"""V9 remaining WorkBuddy parity unit tests (stdlib only)."""

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
from octop.contrib.workbuddy.console_server import api_payload
from octop.contrib.workbuddy.cowrite import CowriteStore
from octop.contrib.workbuddy.data import export_workspace, import_workspace
from octop.contrib.workbuddy.gitwork import WorktreeManager
from octop.contrib.workbuddy.inspiration import InspirationCatalog
from octop.contrib.workbuddy.knowledge import LocalKnowledgeBase
from octop.contrib.workbuddy.library import LibraryIndex
from octop.contrib.workbuddy.models_profile import ModelProfile, ModelProfileStore
from octop.contrib.workbuddy.security import PolicyStore, SecurityPolicy
from octop.contrib.workbuddy.skills.market import install_skill, scan_skill_dir
from octop.contrib.workbuddy.task import TaskStore
from octop.contrib.workbuddy.bench.harbor import harbor_score_entry, harness_mount_probe
from octop.contrib.workbuddy.hub import hub_status
from octop.contrib.workbuddy.connectors.china_im import (
    InboxStore,
    WeChatConnector,
    QQConnector,
    resolve_message_china_im,
)


class TestV91TaskLifecycle(unittest.TestCase):
    def test_create_append_complete(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = TaskStore(tmp)
            rec = store.create("demo", prompt="hello", mode="plan")
            self.assertEqual(rec.status, "pending")
            self.assertEqual(len(rec.messages), 1)
            store.append_message(rec.task_id, "assistant", "hi")
            rec2 = store.get(rec.task_id)
            self.assertEqual(rec2.status, "running")
            done = store.complete(rec.task_id, summary="ok")
            self.assertEqual(done.status, "completed")
            self.assertEqual(len(store.list_tasks()), 1)


class TestV92Policy(unittest.TestCase):
    def test_policy_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "policy.json"
            store = PolicyStore(path)
            store.save(SecurityPolicy(default_mode="ask", allow_shell=False))
            pol = store.load()
            self.assertEqual(pol.default_mode, "ask")
            self.assertFalse(pol.allows_tool("shell_exec"))
            self.assertTrue(pol.allows_tool("read_file"))


class TestV93DataExport(unittest.TestCase):
    def test_export_import(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "src"
            src.mkdir()
            (src / "a.txt").write_text("hello", encoding="utf-8")
            archive = Path(tmp) / "out.zip"
            export_workspace(src, archive)
            dest = Path(tmp) / "dest"
            result = import_workspace(archive, dest)
            self.assertGreaterEqual(result["file_count"], 1)
            self.assertTrue((dest / "a.txt").is_file())


class TestV94ModelProfile(unittest.TestCase):
    def test_profiles(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = ModelProfileStore(Path(tmp) / "p.json")
            store.upsert(ModelProfile("local", "http://127.0.0.1:8000/v1", "qwen"))
            self.assertEqual(store.active().profile_id, "local")
            self.assertEqual(len(store.list()), 1)


class TestV95Worktree(unittest.TestCase):
    def test_dry_register(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            mgr = WorktreeManager(ROOT, Path(tmp) / "reg.json")
            info = mgr.register_only(str(Path(tmp) / "wt"), "feature/x", task_id="t1")
            self.assertEqual(info.branch, "feature/x")
            self.assertEqual(len(mgr.list()), 1)
            self.assertTrue(mgr.remove(info.path, dry_run=True))


class TestV96ChinaIM(unittest.TestCase):
    def test_probe_and_gate(self) -> None:
        self.assertFalse(WeChatConnector(webhook="").configured())
        self.assertFalse(QQConnector(webhook="").configured())
        r = resolve_message_china_im("wechat:webhook", "hi", require_outbound_flag=True)
        self.assertIsNotNone(r)
        self.assertFalse(r.ok)
        with tempfile.TemporaryDirectory() as tmp:
            inbox = InboxStore(Path(tmp) / "inbox.jsonl")
            inbox.append("wechat", {"text": "ping"})
            self.assertEqual(len(inbox.read_tail()), 1)


class TestV97Library(unittest.TestCase):
    def test_index_publish(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            lib = LibraryIndex(tmp)
            src = Path(tmp) / "note.md"
            src.write_text("# hi", encoding="utf-8")
            # put source outside content dir
            src2 = Path(tmp) / "incoming.md"
            src2.write_text("# note", encoding="utf-8")
            entry = lib.add_file(src2, title="Note")
            self.assertTrue(entry.sha256)
            out = lib.publish()
            self.assertTrue(out.is_file())
            self.assertIn("Note", out.read_text(encoding="utf-8"))


class TestV98Inspiration(unittest.TestCase):
    def test_scaffold(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cat = InspirationCatalog()
            rows = cat.list()
            self.assertGreaterEqual(len(rows), 3)
            dest = Path(tmp) / "app"
            cat.scaffold("daily-brief", dest)
            self.assertTrue((dest / "SOUL.md").is_file())
            self.assertTrue((dest / "buddy.json").is_file())


class TestV99Knowledge(unittest.TestCase):
    def test_ingest_search(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            kb = LocalKnowledgeBase(tmp)
            doc = Path(tmp) / "doc.md"
            doc.write_text("WorkBuddy 知识库对齐 local RAG milvus", encoding="utf-8")
            kb.ingest_file(doc)
            hits = kb.search("知识库")
            self.assertGreaterEqual(len(hits), 1)
            dry = kb.upsert_milvus_dry()
            self.assertTrue(dry["dry_run"])


class TestV910Cowrite(unittest.TestCase):
    def test_session(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = CowriteStore(tmp)
            s = store.start("doc", seed="标题\n")
            store.append(s.session_id, "human", "第一段")
            store.append(s.session_id, "assistant", "润色段落")
            out = Path(tmp) / "export.md"
            store.export_markdown(s.session_id, out)
            text = out.read_text(encoding="utf-8")
            self.assertIn("第一段", text)


class TestV911Bridge(unittest.TestCase):
    def test_gate_and_create(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = TaskStore(tmp)
            blocked = ChannelBridge(store, allow=False).handle_inbound("wechat", "hi")
            self.assertFalse(blocked.ok)
            ok = ChannelBridge(store, allow=True).handle_inbound("wechat", "/task 写周报")
            self.assertTrue(ok.ok)
            self.assertTrue(ok.task_id)
            append = ChannelBridge(store, allow=True).handle_inbound(
                "qq", f"/append {ok.task_id} 补充材料"
            )
            self.assertTrue(append.ok)


class TestV912SkillMarket(unittest.TestCase):
    def test_scan_install(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            skill = Path(tmp) / "demo-skill"
            skill.mkdir()
            (skill / "SKILL.md").write_text(
                "---\nname: demo\ndescription: x\n---\n# Demo\n", encoding="utf-8"
            )
            report = scan_skill_dir(skill)
            self.assertTrue(report.ok)
            dest = Path(tmp) / "installed"
            result = install_skill(skill, dest)
            self.assertTrue(result["installed"])
            self.assertTrue((dest / "demo-skill" / "SKILL.md").is_file())


class TestV913ConsoleApi(unittest.TestCase):
    def test_api_payload_shapes(self) -> None:
        status = api_payload("/api/status")
        self.assertTrue(status.get("ok"))
        self.assertGreaterEqual(int(status.get("v") or 0), 9)
        tasks = api_payload("/api/tasks")
        self.assertIn("tasks", tasks)
        skills = api_payload("/api/skills")
        self.assertIn("skills", skills)
        connectors = api_payload("/api/connectors")
        self.assertTrue(connectors.get("ok"))
        harbor = api_payload("/api/harbor")
        self.assertIn("status", harbor)


class TestV914HarborScore(unittest.TestCase):
    def test_harness_and_dry_score(self) -> None:
        probe = harness_mount_probe(root=ROOT)
        self.assertTrue(probe["ok"])
        score = harbor_score_entry(root=ROOT, dry_run=True)
        self.assertTrue(score["ok"])
        self.assertEqual(score["mode"], "dry_run")


class TestV915AuditHooks(unittest.TestCase):
    def test_task_create_audits(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            import os

            os.environ["WB_AUDIT_LOG"] = str(Path(tmp) / "audit.jsonl")
            # reset singleton
            import octop.contrib.workbuddy.audit.log as audit_log

            audit_log._default = None
            store = TaskStore(Path(tmp) / "tasks")
            store.create("audited")
            lines = Path(os.environ["WB_AUDIT_LOG"]).read_text(encoding="utf-8").strip().splitlines()
            self.assertGreaterEqual(len(lines), 1)
            row = json.loads(lines[-1])
            self.assertEqual(row["action"], "task.create")


class TestV9Hub(unittest.TestCase):
    def test_hub_v9(self) -> None:
        data = hub_status(root=ROOT)
        self.assertGreaterEqual(int(data["v"]), 9)
        self.assertIn("harness", data)
        self.assertIn("tasks", data)
        self.assertIn("/api/tasks", data["console"]["apis"])


if __name__ == "__main__":
    unittest.main()
