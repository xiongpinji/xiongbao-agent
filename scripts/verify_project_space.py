# SPDX-License-Identifier: MIT
"""Verify project space + skill deposit + run_task binding."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

CONSOLE = ROOT / "octop" / "contrib" / "workbuddy" / "console"
SHELL = CONSOLE / "shell.html"


class ProjectSpaceApiTests(unittest.TestCase):
    def test_shell_has_project_ui(self) -> None:
        html = SHELL.read_text(encoding="utf-8")
        self.assertIn("btnProjects", html)
        self.assertIn("projectSelect", html)
        self.assertIn("存入项目", html)
        self.assertIn("project_id", html)
        self.assertIn("/api/projects", html)

    def test_console_routes(self) -> None:
        src = (ROOT / "octop" / "contrib" / "workbuddy" / "console_server.py").read_text(encoding="utf-8")
        self.assertIn('"/api/projects"', src)
        self.assertIn("api_get_project_path", src)
        self.assertIn("skills/deposit", src)
        self.assertIn("projects_root", src)

    def test_deposit_and_bind_on_run(self) -> None:
        from octop.contrib.workbuddy.project import ProjectSpace
        from octop.contrib.workbuddy.runtime.task_runner import run_task
        from octop.contrib.workbuddy.security import PolicyStore, SecurityPolicy
        from octop.contrib.workbuddy.task import TaskStore

        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            projects = base / "projects"
            tasks = base / "tasks"
            goals = base / "goals"
            space = ProjectSpace(projects)
            space.create("acme_space", name="Acme Space")
            skill = base / "expert-skill"
            skill.mkdir()
            (skill / "SKILL.md").write_text(
                "---\nname: Expert Skill\ndescription: project expert\n---\n\n# Expert\nAlways mention PROJECT_EXPERT_TOKEN.\n",
                encoding="utf-8",
            )
            space.deposit_skill("acme_space", skill)
            self.assertIn("expert-skill", space.list_skills("acme_space"))

            store = TaskStore(tasks)
            rec = store.create(
                "use expert",
                prompt="写一个 out.md",
                mode="craft",
                project_id="acme_space",
            )
            policy = base / "policy.json"
            PolicyStore(policy).save(SecurityPolicy(default_mode="craft"))
            result = run_task(
                rec.task_id,
                tasks_root=tasks,
                goals_root=goals,
                projects_root=projects,
                policy_path=policy,
                kb_root=None,
                dry_run=False,
            )
            self.assertTrue(result.ok)
            self.assertIn("expert-skill", result.detail.get("bound_skills") or [])
            texts = " ".join(m.content for m in store.get(rec.task_id).messages)
            self.assertIn("expert-skill", texts)
            out = tasks / rec.task_id / "workspace" / "files" / "out.md"
            self.assertTrue(out.is_file(), out)
            # skill context is embedded into write artifact body by planner
            body = out.read_text(encoding="utf-8")
            self.assertIn("Bound Skills", body)
            self.assertIn("PROJECT_EXPERT_TOKEN", body)
            self.assertIn("Enabled Skills", body)

    def test_tenant_projects_root(self) -> None:
        from octop.contrib.workbuddy.tenant import TenantRoots

        roots = TenantRoots("t1", "u1", base=Path("artifacts"))
        self.assertTrue(str(roots.projects).endswith("tenants/t1/projects") or "tenants" in str(roots.projects).replace("\\", "/"))
        self.assertIn("projects", roots.to_dict())


def main() -> int:
    print("=" * 60)
    print("▶ project-space unit tests")
    print("=" * 60)
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(ProjectSpaceApiTests)
    result = unittest.TextTestRunner(verbosity=1).run(suite)
    if not result.wasSuccessful():
        return 1
    print("OK project-space unit tests")
    print("\nVERIFY PROJECT SPACE OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
