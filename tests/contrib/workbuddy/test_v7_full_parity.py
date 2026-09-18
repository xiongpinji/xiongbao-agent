# SPDX-License-Identifier: MIT
"""V7 full-parity unit tests (stdlib, no live network)."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from octop.contrib.workbuddy.audit import AuditLog
from octop.contrib.workbuddy.enterprise import casdoor
from octop.contrib.workbuddy.modes.assembler import assemble_system_prompt
from octop.contrib.workbuddy.office import deliver_bundle, write_markdown
from octop.contrib.workbuddy.project import ProjectSpace
from octop.contrib.workbuddy.templates.nunjucks_lite import render


class TestNunjucksLite(unittest.TestCase):
    def test_if_else_var(self) -> None:
        tpl = "{% if Flag %}yes {{ Name }}{% else %}no{% endif %}"
        self.assertEqual(render(tpl, {"Flag": "1", "Name": "A"}).strip(), "yes A")
        self.assertEqual(render(tpl, {"Flag": "", "Name": "A"}).strip(), "no")

    def test_official_ask_tpl_renders(self) -> None:
        assembled = assemble_system_prompt(
            mode="ask",
            soul="I am a helper",
            user_profile="User is Alice",
            use_official_tpl=True,
            model_name="test-model",
        )
        self.assertIn("Ask mode", assembled.system)
        self.assertIn("test-model", assembled.system)
        self.assertIn("I am a helper", assembled.system)


class TestCasdoorJwt(unittest.TestCase):
    def test_hs256_roundtrip(self) -> None:
        header = base64.urlsafe_b64encode(b'{"alg":"HS256","typ":"JWT"}').rstrip(b"=").decode()
        payload = base64.urlsafe_b64encode(b'{"sub":"u1","exp":9999999999}').rstrip(b"=").decode()
        secret = "test-secret"
        sig = hmac.new(
            secret.encode(), f"{header}.{payload}".encode(), hashlib.sha256
        ).digest()
        token = f"{header}.{payload}.{base64.urlsafe_b64encode(sig).rstrip(b'=').decode()}"
        data = casdoor.verify_hs256(token, secret)
        self.assertEqual(data["sub"], "u1")


class TestProjectSpace(unittest.TestCase):
    def test_create_deposit_shared(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            space = ProjectSpace(tmp)
            meta = space.create("p1", name="P1", members=["a"])
            self.assertEqual(meta.project_id, "p1")
            skill = Path(tmp) / "_src_skill"
            skill.mkdir()
            (skill / "SKILL.md").write_text("# skill\n", encoding="utf-8")
            dest = space.deposit_skill("p1", skill)
            self.assertTrue(dest.is_dir())
            path = space.write_shared("p1", "notes/hi.md", "hello")
            self.assertTrue(path.is_file())
            self.assertEqual(space.list_skills("p1"), ["_src_skill"])


class TestOfficeAndAudit(unittest.TestCase):
    def test_bundle_and_audit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            results = deliver_bundle(
                base / "out",
                title="T",
                body="Body",
                table_rows=[("a", "b"), ("1", "2")],
                slides=[("S1", "x")],
            )
            self.assertTrue(any(r.kind == "markdown" for r in results))
            write_markdown(base / "x.md", "X", "y")
            log = AuditLog(base / "a.jsonl")
            log.emit("test", foo=1)
            tail = log.read_tail(5)
            self.assertEqual(tail[-1]["action"], "test")


class TestHarborModuleImport(unittest.TestCase):
    def test_status_dict(self) -> None:
        from octop.contrib.workbuddy.bench.harbor import harbor_status

        st = harbor_status()
        d = st.to_dict()
        self.assertIn("docker_available", d)
        self.assertIn("subsets", d)


if __name__ == "__main__":
    unittest.main()
