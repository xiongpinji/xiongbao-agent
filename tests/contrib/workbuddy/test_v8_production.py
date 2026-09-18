# SPDX-License-Identifier: MIT
"""V8 production-path unit tests (stdlib; no live Harbor run required)."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from octop.contrib.workbuddy.bench.harbor import harbor_status, venv_python
from octop.contrib.workbuddy.hub import hub_status


class TestV8HarborVenv(unittest.TestCase):
    def test_venv_detected_after_sync(self) -> None:
        py = venv_python(ROOT)
        # May be absent on fresh CI clones without uv sync — then skip soft assert
        if py is None:
            self.skipTest("vendor/workbuddy-bench/.venv not present")
        self.assertTrue(py.is_file())
        status = harbor_status(ROOT)
        self.assertTrue(status.bench_synced)
        self.assertTrue(status.python_ok_for_harbor)

    def test_smoke_job_yaml_exists(self) -> None:
        job = ROOT / "vendor" / "workbuddy-bench" / "configs" / "jobs" / "local-openai-cbc-office-smoke.yaml"
        model = ROOT / "vendor" / "workbuddy-bench" / "configs" / "models" / "local-openai.yaml"
        self.assertTrue(job.is_file(), str(job))
        self.assertTrue(model.is_file(), str(model))


class TestV8Hub(unittest.TestCase):
    def test_hub_status_shape(self) -> None:
        data = hub_status(root=ROOT)
        self.assertTrue(data["ok"])
        self.assertIn("harbor", data)
        self.assertIn("enterprise", data)
        self.assertIn("compose", data)
        self.assertEqual(data["console"]["default_port"], 8010)
        # JSON serializable
        json.dumps(data)


class TestV8ConsoleStatic(unittest.TestCase):
    def test_index_html(self) -> None:
        path = ROOT / "octop" / "contrib" / "workbuddy" / "console" / "index.html"
        self.assertTrue(path.is_file())
        text = path.read_text(encoding="utf-8")
        self.assertIn("/api/status", text)
        self.assertIn("WorkBuddy Console", text)


class TestV8Compose(unittest.TestCase):
    def test_compose_mentions_console(self) -> None:
        path = ROOT / "deploy" / "docker-compose.workbuddy.yml"
        text = path.read_text(encoding="utf-8")
        self.assertIn("wb-console", text)
        self.assertIn("8010", text)
        self.assertIn('profiles: ["full"]', text)


if __name__ == "__main__":
    unittest.main()
