# SPDX-License-Identifier: MIT
"""V11 multi-tenant isolation unit tests."""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from http.client import HTTPConnection
from pathlib import Path
from threading import Thread

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from octop.contrib.workbuddy.console_server import serve
from octop.contrib.workbuddy.hub import hub_status
from octop.contrib.workbuddy.task import TaskStore
from octop.contrib.workbuddy.tenant import (
    TenantQuota,
    TenantRegistry,
    TenantRoots,
    backup_tenant,
    check_can_create_task,
    issue_token,
    restore_tenant,
    tenant_collection,
    verify_token,
)
from octop.contrib.workbuddy.tenant.quota import QuotaExceeded


class TenantIsolationTests(unittest.TestCase):
    def setUp(self) -> None:
        self._td = tempfile.TemporaryDirectory()
        self.base = Path(self._td.name)
        self.reg_path = self.base / "_registry.json"
        self.reg = TenantRegistry(self.reg_path)
        os.environ["WB_ARTIFACTS_ROOT"] = str(self.base)
        os.environ["WB_CONSOLE_SECRET"] = "test-secret-v11"

    def tearDown(self) -> None:
        self._td.cleanup()
        os.environ.pop("WB_ARTIFACTS_ROOT", None)

    def test_paths_do_not_overlap(self) -> None:
        a = TenantRoots("acme", "u1", base=self.base)
        b = TenantRoots("globex", "u1", base=self.base)
        a.ensure()
        b.ensure()
        self.assertNotEqual(a.tasks, b.tasks)
        self.assertTrue(str(a.root).endswith(str(Path("tenants") / "acme" / "users" / "u1")))

    def test_create_login_jwt(self) -> None:
        rec, key = self.reg.create("acme", name="Acme", admin_user_id="admin")
        self.assertEqual(rec.tenant_id, "acme")
        ctx = self.reg.authenticate("acme", "admin", key)
        token = issue_token(ctx)
        again = verify_token(token)
        self.assertEqual(again.tenant_id, "acme")
        self.assertEqual(again.user_id, "admin")

    def test_cross_tenant_tasks_isolated(self) -> None:
        _, key_a = self.reg.create("acme", admin_user_id="admin")
        _, key_b = self.reg.create("globex", admin_user_id="admin")
        roots_a = TenantRoots("acme", "admin", base=self.base)
        roots_b = TenantRoots("globex", "admin", base=self.base)
        roots_a.ensure()
        roots_b.ensure()
        TaskStore(roots_a.tasks).create("secret-a", task_id="t-a", prompt="hi")
        TaskStore(roots_b.tasks).create("secret-b", task_id="t-b", prompt="hi")
        ids_a = {t.task_id for t in TaskStore(roots_a.tasks).list_tasks()}
        ids_b = {t.task_id for t in TaskStore(roots_b.tasks).list_tasks()}
        self.assertEqual(ids_a, {"t-a"})
        self.assertEqual(ids_b, {"t-b"})
        self.assertNotIn("t-a", ids_b)
        _ = key_a, key_b

    def test_quota_blocks(self) -> None:
        rec, _ = self.reg.create("tiny", admin_user_id="admin")
        self.reg.set_quota("tiny", TenantQuota(max_tasks=1, max_storage_mb=100))
        rec = self.reg.get("tiny")
        assert rec is not None
        roots = TenantRoots("tiny", "admin", base=self.base)
        roots.ensure()
        TaskStore(roots.tasks).create("one", task_id="t1", prompt="x")
        with self.assertRaises(QuotaExceeded):
            check_can_create_task(rec, roots)

    def test_milvus_ns(self) -> None:
        self.assertEqual(tenant_collection("Acme-Corp"), "wb_acme_corp")
        self.assertTrue(tenant_collection("9bad").startswith("wb_t_"))

    def test_backup_restore(self) -> None:
        self.reg.create("acme", admin_user_id="admin")
        roots = TenantRoots("acme", "admin", base=self.base)
        roots.ensure()
        (roots.tasks / "marker.txt").write_text("hello", encoding="utf-8")
        archive = self.base / "acme.zip"
        backup_tenant("acme", archive, registry=self.reg, base=self.base)
        # wipe and restore
        import shutil

        shutil.rmtree(self.base / "tenants" / "acme")
        restore_tenant(archive, registry=self.reg, base=self.base, overwrite=True)
        self.assertTrue((roots.tasks / "marker.txt").is_file())
        self.assertIsNotNone(self.reg.get("acme"))

    def test_hub_v11(self) -> None:
        data = hub_status(root=ROOT)
        self.assertGreaterEqual(int(data["v"]), 11)
        self.assertIn("tenants", data)


class ConsoleAuthTests(unittest.TestCase):
    def setUp(self) -> None:
        self._td = tempfile.TemporaryDirectory()
        self.base = Path(self._td.name)
        os.environ["WB_ARTIFACTS_ROOT"] = str(self.base)
        os.environ["WB_CONSOLE_SECRET"] = "console-test-secret"
        os.environ["WB_MULTI_TENANT"] = "1"
        os.environ["WB_CONSOLE_AUTH"] = "1"
        os.environ["WB_TENANT_REGISTRY"] = str(self.base / "_registry.json")
        self.reg = TenantRegistry(self.base / "_registry.json")
        _, self.api_key = self.reg.create("acme", admin_user_id="admin")
        self.port = 18010
        self._thread = Thread(target=serve, kwargs={"host": "127.0.0.1", "port": self.port}, daemon=True)
        self._thread.start()
        import time

        time.sleep(0.3)

    def tearDown(self) -> None:
        os.environ.pop("WB_MULTI_TENANT", None)
        os.environ.pop("WB_CONSOLE_AUTH", None)
        os.environ.pop("WB_ARTIFACTS_ROOT", None)
        os.environ.pop("WB_TENANT_REGISTRY", None)
        self._td.cleanup()

    def test_health_public_tasks_401(self) -> None:
        conn = HTTPConnection("127.0.0.1", self.port, timeout=3)
        conn.request("GET", "/api/health")
        resp = conn.getresponse()
        body = json.loads(resp.read().decode("utf-8"))
        self.assertEqual(resp.status, 200)
        self.assertTrue(body.get("auth_required"))

        conn.request("GET", "/api/tasks")
        resp = conn.getresponse()
        self.assertEqual(resp.status, 401)
        conn.close()

    def test_login_and_scoped_tasks(self) -> None:
        conn = HTTPConnection("127.0.0.1", self.port, timeout=3)
        payload = json.dumps(
            {"tenant_id": "acme", "user_id": "admin", "api_key": self.api_key}
        ).encode("utf-8")
        conn.request(
            "POST",
            "/api/auth/login",
            body=payload,
            headers={"Content-Type": "application/json"},
        )
        resp = conn.getresponse()
        data = json.loads(resp.read().decode("utf-8"))
        self.assertEqual(resp.status, 200)
        self.assertTrue(data.get("ok"))
        token = data["token"]

        roots = TenantRoots("acme", "admin", base=self.base)
        roots.ensure()
        TaskStore(roots.tasks).create("demo", task_id="demo1", prompt="hi")

        conn.request("GET", "/api/tasks", headers={"Authorization": f"Bearer {token}"})
        resp = conn.getresponse()
        tasks = json.loads(resp.read().decode("utf-8"))
        self.assertEqual(resp.status, 200)
        ids = {t["task_id"] for t in tasks.get("tasks", [])}
        self.assertIn("demo1", ids)
        conn.close()


if __name__ == "__main__":
    unittest.main()
