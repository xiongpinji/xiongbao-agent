# SPDX-License-Identifier: MIT
"""Customer acceptance playbook — login → project → skill → run → download → ACL.

In-process (default) — no live server required::

    python -S scripts/verify_customer_playbook.py

Optional live HTTP against console::

    set WB_PLAYBOOK_BASE=http://127.0.0.1:8010
    set WB_PLAYBOOK_TID=...
    set WB_PLAYBOOK_UID=admin
    set WB_PLAYBOOK_KEY=...
    python -S scripts/verify_customer_playbook.py --live
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from urllib import error, request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


class CustomerPlaybookTests(unittest.TestCase):
    def test_playbook_in_process(self) -> None:
        from octop.contrib.workbuddy.channel_inbound import ingest_to_task, parse_inbound_body
        from octop.contrib.workbuddy.console_parity_api import normalize_members, require_role, save_project_meta
        from octop.contrib.workbuddy.console_workspace import resolve_download
        from octop.contrib.workbuddy.ops_health import health_detail, task_replay
        from octop.contrib.workbuddy.project import ProjectSpace
        from octop.contrib.workbuddy.runtime.task_runner import run_task
        from octop.contrib.workbuddy.security import PolicyStore, SecurityPolicy
        from octop.contrib.workbuddy.task import TaskStore
        from octop.contrib.workbuddy.tenant import (
            TenantRegistry,
            TenantRoots,
            issue_token,
            verify_token,
        )
        from octop.contrib.workbuddy.tenant.models import TenantQuota

        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            os.environ["WB_ARTIFACTS_ROOT"] = str(base)
            os.environ["WB_CONSOLE_SECRET"] = "playbook-secret"

            reg = TenantRegistry(base / "_registry.json")
            rec, key = reg.create("acme_demo", name="验收客户")
            ctx = reg.authenticate("acme_demo", "admin", key)
            tok = issue_token(ctx)
            self.assertEqual(verify_token(tok).tenant_id, "acme_demo")

            roots = TenantRoots("acme_demo", "admin", base=base)
            roots.ensure()

            # 1) project + owner
            space = ProjectSpace(roots.projects)
            meta = space.create(
                "demo_proj",
                name="验收项目",
                members=[{"user_id": "admin", "role": "owner"}],
            )
            meta.members = normalize_members(list(meta.members or []))
            save_project_meta(space, meta)

            # 2) deposit skill
            skill = base / "accept-skill"
            skill.mkdir()
            (skill / "SKILL.md").write_text(
                "---\nname: Accept Skill\ndescription: acceptance\n---\n\n# Accept\nMention ACCEPT_TOKEN.\n",
                encoding="utf-8",
            )
            space.deposit_skill("demo_proj", skill)
            self.assertIn("accept-skill", space.list_skills("demo_proj"))

            # 3) member ACL — viewer cannot pass editor gate
            meta.members = normalize_members(
                [
                    {"user_id": "admin", "role": "owner"},
                    {"user_id": "viewer1", "role": "viewer"},
                    {"user_id": "editor1", "role": "editor"},
                ]
            )
            save_project_meta(space, meta)
            ok_v, _ = require_role(space, "demo_proj", "viewer1", "editor")
            self.assertFalse(ok_v)
            ok_e, role_e = require_role(space, "demo_proj", "editor1", "editor")
            self.assertTrue(ok_e)
            self.assertEqual(role_e, "editor")

            # 4) real run → artifact
            store = TaskStore(roots.tasks)
            task = store.create(
                "验收执行",
                prompt="写一个 accept_out.md",
                mode="craft",
                project_id="demo_proj",
            )
            policy = base / "policy.json"
            PolicyStore(policy).save(SecurityPolicy(default_mode="craft"))
            result = run_task(
                task.task_id,
                tasks_root=roots.tasks,
                goals_root=base / "goals",
                projects_root=roots.projects,
                policy_path=policy,
                dry_run=False,
            )
            self.assertTrue(result.ok, result.detail)
            task_dir = store._dir(task.task_id)  # noqa: SLF001
            out = task_dir / "workspace" / "files" / "accept_out.md"
            self.assertTrue(out.is_file(), out)

            # 5) download resolve
            target, err = resolve_download(task_dir, "workspace/files/accept_out.md")
            self.assertEqual(err, "")
            self.assertTrue(target and target.is_file())

            # 6) replay pack
            replay = task_replay(task_dir, store=store, task_id=task.task_id)
            self.assertGreaterEqual(replay["event_count"], 1)
            self.assertEqual(replay["status"], "completed")

            # 7) channel inbound → task
            msg = parse_inbound_body(
                {"channel": "feishu", "text": "帮我写周报", "sender": "u_feishu"}
            )
            inbound = ingest_to_task(msg, tasks_root=roots.tasks, project_id="demo_proj")
            self.assertTrue(inbound["ok"])
            self.assertTrue(store.get(inbound["task_id"]).project_id == "demo_proj")

            # 8) quota fence
            reg.set_quota("acme_demo", TenantQuota(max_tasks=1, max_users=10, max_storage_mb=1024))
            # already have >=1 tasks; creating more should fail check
            from octop.contrib.workbuddy.tenant import check_can_create_task
            from octop.contrib.workbuddy.tenant.quota import QuotaExceeded

            rec2 = reg.get("acme_demo")
            assert rec2 is not None
            # bump max to current count then assert exceed on next
            n_tasks = sum(1 for p in roots.tasks.iterdir() if (p / "task.json").is_file())
            reg.set_quota(
                "acme_demo",
                TenantQuota(max_tasks=n_tasks, max_users=10, max_storage_mb=1024),
            )
            rec2 = reg.get("acme_demo")
            assert rec2 is not None
            with self.assertRaises(QuotaExceeded):
                check_can_create_task(rec2, roots)

            # 9) health detail shape
            h = health_detail(auth_required=True, model="qwen2.5:3b")
            self.assertTrue(h["ok"])
            self.assertIn("uptime_s", h)
            self.assertIn("restart_hint", h)

            print(
                json.dumps(
                    {
                        "playbook": "ok",
                        "tenant": "acme_demo",
                        "project": "demo_proj",
                        "task": task.task_id,
                        "inbound": inbound["task_id"],
                        "artifact": str(out),
                    },
                    ensure_ascii=False,
                )
            )


def _live_http() -> int:
    base = (os.environ.get("WB_PLAYBOOK_BASE") or "http://127.0.0.1:8010").rstrip("/")
    tid = os.environ.get("WB_PLAYBOOK_TID") or ""
    uid = os.environ.get("WB_PLAYBOOK_UID") or "admin"
    key = os.environ.get("WB_PLAYBOOK_KEY") or ""
    if not tid or not key:
        print("LIVE SKIP: set WB_PLAYBOOK_TID / WB_PLAYBOOK_KEY")
        return 0

    def call(method: str, path: str, body: dict | None = None, token: str = "") -> dict:
        data = None if body is None else json.dumps(body).encode("utf-8")
        req = request.Request(
            base + path,
            data=data,
            method=method,
            headers={
                "Content-Type": "application/json",
                **({"Authorization": "Bearer " + token} if token else {}),
            },
        )
        try:
            with request.urlopen(req, timeout=120) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except error.HTTPError as exc:
            raw = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"{method} {path} → {exc.code}: {raw}") from exc

    health = call("GET", "/api/health")
    assert health.get("ok"), health
    login = call(
        "POST",
        "/api/auth/login",
        {"tenant_id": tid, "user_id": uid, "api_key": key},
    )
    token = login["token"]
    proj_id = "live_accept_" + tid[:8]
    try:
        call(
            "POST",
            "/api/projects",
            {"project_id": proj_id, "name": "现场验收项目"},
            token,
        )
    except RuntimeError as exc:
        if "409" not in str(exc) and "exists" not in str(exc).lower():
            raise
    skills = call("GET", "/api/skills", token=token)
    skill_id = (skills.get("skills") or [{}])[0].get("id")
    if skill_id:
        try:
            call("POST", "/api/skills/install", {"skill_id": skill_id}, token)
        except RuntimeError:
            pass
        try:
            call(
                "POST",
                f"/api/projects/{proj_id}/skills/deposit",
                {"skill_id": skill_id},
                token,
            )
        except RuntimeError as exc:
            print("deposit warn:", exc)
    task = call(
        "POST",
        "/api/tasks",
        {"title": "现场验收任务", "mode": "craft", "project_id": proj_id, "prompt": "写一个 live_accept.md"},
        token,
    )
    tid_task = task["task"]["task_id"]
    call(
        "POST",
        f"/api/tasks/{tid_task}/messages",
        {"content": "写一个 live_accept.md", "run": True, "dry": False, "stream": False},
        token,
    )
    detail = call("GET", f"/api/tasks/{tid_task}", token=token)
    ws = call("GET", f"/api/tasks/{tid_task}/workspace", token=token)
    replay = call("GET", f"/api/tasks/{tid_task}/replay", token=token)
    inbound = call(
        "POST",
        "/api/channels/inbound",
        {"channel": "feishu", "text": "现场通道验收", "sender": "live", "run": False},
        token,
    )
    print(
        json.dumps(
            {
                "live": "ok",
                "health": health.get("v"),
                "task": tid_task,
                "status": detail.get("task", {}).get("status"),
                "files": len(ws.get("files") or []),
                "replay_events": replay.get("event_count"),
                "inbound": inbound.get("task_id"),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    argv = list(argv or sys.argv[1:])
    if "--live" in argv:
        return _live_http()
    print("=" * 60)
    print("▶ customer playbook (in-process)")
    print("=" * 60)
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(CustomerPlaybookTests)
    result = unittest.TextTestRunner(verbosity=1).run(suite)
    if not result.wasSuccessful():
        return 1
    print("OK customer playbook")
    print("\nVERIFY CUSTOMER PLAYBOOK OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
