# SPDX-License-Identifier: MIT
"""Verify V16 four-subset Harbor jobs + Casdoor/TLS docs exist."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

SMOKE_JOBS = [
    "local-openai-cbc-office-smoke",
    "local-openai-cbc-code-smoke",
    "local-openai-cbc-web-smoke",
    "local-openai-cbc-sec-smoke",
]


class V16Tests(unittest.TestCase):
    def test_smoke_job_yamls(self) -> None:
        jobs = ROOT / "vendor" / "workbuddy-bench" / "configs" / "jobs"
        for name in SMOKE_JOBS:
            path = jobs / f"{name}.yaml"
            self.assertTrue(path.is_file(), path)
            text = path.read_text(encoding="utf-8")
            self.assertIn("local-openai", text)
            self.assertIn("task_selection", text)

    def test_web_judge_override(self) -> None:
        path = (
            ROOT
            / "vendor"
            / "workbuddy-bench"
            / "configs"
            / "jobs"
            / "local-openai-cbc-web-smoke.yaml"
        )
        text = path.read_text(encoding="utf-8")
        self.assertIn("llm_judge_override", text)
        self.assertIn("enabled: false", text)

    def test_four_subset_runner_import(self) -> None:
        import importlib.util

        path = ROOT / "scripts" / "run_harbor_four_subsets.py"
        spec = importlib.util.spec_from_file_location("run_harbor_four_subsets", path)
        assert spec and spec.loader
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        self.assertEqual(len(mod.SMOKE_JOBS), 4)
        self.assertEqual(len(mod.FULL_JOBS), 4)

    def test_docs(self) -> None:
        self.assertTrue((ROOT / "deploy" / "enterprise" / "CASDOOR_PRODUCTION.md").is_file())
        self.assertTrue((ROOT / "deploy" / "enterprise" / "HARBOR_FOUR_SUBSETS.md").is_file())
        caddy = (ROOT / "deploy" / "caddy" / "Caddyfile").read_text(encoding="utf-8")
        self.assertIn("tls internal", caddy)

    def test_stage_helper_present(self) -> None:
        src = (
            ROOT
            / "vendor"
            / "workbuddy-bench"
            / "src"
            / "workbuddy_bench"
            / "runner"
            / "resolve_manifest.py"
        )
        text = src.read_text(encoding="utf-8")
        self.assertIn("WB_STAGE_ROOT", text)
        self.assertIn("_win_long", text)


def main() -> int:
    print("=" * 60)
    print("▶ v16 unit tests")
    print("=" * 60)
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(V16Tests)
    result = unittest.TextTestRunner(verbosity=1).run(suite)
    if not result.wasSuccessful():
        return 1
    print("OK v16 unit tests")
    print("\nVERIFY V16 OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
