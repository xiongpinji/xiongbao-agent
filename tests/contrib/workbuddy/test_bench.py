# SPDX-License-Identifier: MIT
"""Tests for workbuddy smoke bench."""

from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT))

from octop.contrib.workbuddy.bench.metrics import MetricsSink  # noqa: E402
from octop.contrib.workbuddy.bench.runner import BenchRunner  # noqa: E402
from octop.contrib.workbuddy.bench.sample import (  # noqa: E402
    build_smoke_sample,
    default_library_root,
    write_sample_json,
)


def test_sample_size_50() -> None:
    tasks = build_smoke_sample(default_library_root(), n=50)
    assert len(tasks) == 50, f"expected 50, got {len(tasks)}"
    kinds = {t.kind for t in tasks}
    assert "team" in kinds
    assert "agent" in kinds
    team_n = sum(1 for t in tasks if t.kind == "team")
    agent_n = sum(1 for t in tasks if t.kind == "agent")
    assert team_n == 33, team_n
    assert agent_n == 17, agent_n


def test_sample_prompts_nonempty() -> None:
    tasks = build_smoke_sample(n=50)
    empty = [t.task_id for t in tasks if not t.prompt.strip()]
    assert not empty, f"empty prompts: {empty[:5]}"


def test_runner_smoke_subset() -> None:
    tasks = build_smoke_sample(n=50)
    # Run a small subset for unit speed + one known team
    subset = [t for t in tasks if t.expert_id == "StockPartnerTeam"]
    subset += [t for t in tasks if t.kind == "agent"][:2]
    assert subset, "subset empty"
    sink = MetricsSink()
    report = BenchRunner(metrics=sink).run(subset, suite="unit-subset")
    assert report.total == len(subset)
    assert report.passed == report.total, report.to_dict()
    assert any(e.event == "bench.end" for e in sink.events)


def test_write_sample_json(tmp_path: Path | None = None) -> None:
    out = (tmp_path or Path("artifacts/bench")) / "_unit_sample.json"
    if tmp_path is None:
        out = PROJECT / "artifacts" / "bench" / "_unit_sample.json"
    tasks = build_smoke_sample(n=10)
    write_sample_json(tasks, out)
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["count"] == 10
    assert len(data["tasks"]) == 10


def main() -> int:
    tests = [
        test_sample_size_50,
        test_sample_prompts_nonempty,
        test_runner_smoke_subset,
        test_write_sample_json,
    ]
    failed = 0
    for fn in tests:
        try:
            fn()
            print(f"OK  {fn.__name__}")
        except Exception as exc:  # noqa: BLE001
            failed += 1
            print(f"FAIL {fn.__name__}: {exc}")
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
