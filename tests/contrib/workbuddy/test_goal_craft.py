# SPDX-License-Identifier: MIT
"""Unit tests for Goal/Craft (plan → execute → accept). Run: python -S this_file."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from octop.contrib.workbuddy.goal import (  # noqa: E402
    GoalEngine,
    GoalStore,
    accept_all,
    plan_goal,
)
from octop.contrib.workbuddy.goal.acceptor import check_criterion  # noqa: E402
from octop.contrib.workbuddy.goal.models import AcceptanceCriterion  # noqa: E402
from octop.contrib.workbuddy.routine import LiveStepRunner  # noqa: E402


def test_plan_write_and_message() -> None:
    plan = plan_goal("把摘要写入 report.md 并通知飞书")
    kinds = [s.kind for s in plan.steps]
    assert "write" in kinds
    assert "message" in kinds
    checks = {c.check for c in plan.criteria}
    assert "file_exists" in checks
    assert "outbox_message" in checks
    write = next(s for s in plan.steps if s.kind == "write")
    assert "report.md" in write.instruction
    assert "（内容：" in write.instruction


def test_acceptor_file_and_outbox() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        (work / "files").mkdir()
        (work / "outbox").mkdir()
        (work / "files" / "a.md").write_text("hello goal", encoding="utf-8")
        with (work / "outbox" / "messages.jsonl").open("w", encoding="utf-8") as fh:
            fh.write(json.dumps({"target": "feishu:webhook", "content": "x"}) + "\n")

        c1 = AcceptanceCriterion("1", "exists", "file_exists", path="a.md")
        c2 = AcceptanceCriterion("2", "has", "file_contains", path="a.md", substring="goal")
        c3 = AcceptanceCriterion("3", "msg", "outbox_message", target="feishu:webhook")
        ok, results = accept_all([c1, c2, c3], work_dir=work, step_results=[{"index": 0, "ok": True}])
        assert ok
        assert all(r.ok for r in results)

        bad = check_criterion(
            AcceptanceCriterion("4", "miss", "file_exists", path="nope.md"),
            work_dir=work,
            step_results=[],
        )
        assert not bad.ok


def test_engine_accepts_demo_goal() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        store = GoalStore(root)
        engine = GoalEngine(
            store,
            runner_factory=lambda d: LiveStepRunner(d, allow_net=False),
            max_retries=1,
        )
        run = engine.run(
            "把今日 PR 摘要写入 pr-summary.md 并通知飞书群",
            approvals={"all"},
        )
        assert run.ok, (run.status, run.error, run.accept_results)
        assert run.status == "accepted"
        out = root / "work" / run.id / "files" / "pr-summary.md"
        assert out.is_file()
        assert "PR" in out.read_text(encoding="utf-8") or "目标" in out.read_text(encoding="utf-8")
        assert (root / "runs" / f"{run.id}.json").is_file()


def test_engine_rejects_without_approval() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        store = GoalStore(Path(tmp))
        engine = GoalEngine(store, runner_factory=lambda d: LiveStepRunner(d, allow_net=False))
        run = engine.run("写入 x.md 并通知飞书", approvals=set())
        assert not run.ok
        assert run.status == "error"
        assert "approvals" in run.error


def main() -> int:
    tests = [
        ("plan_write_message", test_plan_write_and_message),
        ("acceptor", test_acceptor_file_and_outbox),
        ("engine_accept", test_engine_accepts_demo_goal),
        ("engine_no_approve", test_engine_rejects_without_approval),
    ]
    failed = 0
    for name, fn in tests:
        try:
            fn()
            print(f"PASS  {name}")
        except Exception as exc:  # noqa: BLE001
            failed += 1
            print(f"FAIL  {name}: {exc}")
    print(f"\n=== {len(tests) - failed} passed, {failed} failed ===")
    if failed:
        return 1
    print("ALL GOAL/CRAFT TESTS OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
