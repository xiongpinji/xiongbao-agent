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
    polish_plan_with_llm,
)
from octop.contrib.workbuddy.goal.acceptor import check_criterion  # noqa: E402
from octop.contrib.workbuddy.goal.models import AcceptanceCriterion  # noqa: E402
from octop.contrib.workbuddy.routine import LiveStepRunner  # noqa: E402


class _FakeLLM:
    def __init__(self, payload: dict) -> None:
        self.payload = payload
        self.calls = 0

    def complete(self, *, system: str, user: str) -> str:
        self.calls += 1
        return json.dumps(self.payload, ensure_ascii=False)


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


def test_llm_polish_keeps_structure() -> None:
    base = plan_goal("把摘要写入 report.md 并通知飞书")
    write = next(s for s in base.steps if s.kind == "write")
    msg = next(s for s in base.steps if s.kind == "message")
    fake = _FakeLLM(
        {
            "steps": [
                {
                    "index": write.index,
                    "instruction": "写入交付物（目标：report.md）（内容：# 润色后的周报）",
                },
                {
                    "index": msg.index,
                    "instruction": "发送通知（目标：feishu:webhook）（内容：润色通知）",
                },
            ],
            "criteria": [
                {"id": c.id, "description": f"润色：{c.description}"} for c in base.criteria
            ],
        }
    )
    polished = polish_plan_with_llm(base, caller=fake, fallback_on_error=False)
    assert fake.calls == 1
    assert polished.source == "rules+llm"
    assert len(polished.steps) == len(base.steps)
    assert all(s.requires_approval == b.requires_approval for s, b in zip(polished.steps, base.steps))
    pw = next(s for s in polished.steps if s.kind == "write")
    assert "（目标：report.md）" in pw.instruction
    assert "（内容：" in pw.instruction
    assert "润色" in polished.criteria[0].description

    # Dropping runner markers must fall back to base instruction
    bad = _FakeLLM(
        {
            "steps": [
                {"index": write.index, "instruction": "随便写点东西到 report.md"},
                {"index": msg.index, "instruction": msg.instruction},
            ],
            "criteria": [{"id": c.id, "description": c.description} for c in base.criteria],
        }
    )
    safe = polish_plan_with_llm(base, caller=bad, fallback_on_error=False)
    assert next(s for s in safe.steps if s.kind == "write").instruction == write.instruction


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


def test_engine_bind_skills() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        skills = root / "skills"
        sid = skills / "handoff"
        sid.mkdir(parents=True)
        (sid / "SKILL.md").write_text(
            "---\nname: handoff\ndescription: Handoff skill\n---\n\n# Handoff\n\nPass context carefully.\n",
            encoding="utf-8",
        )
        from octop.contrib.workbuddy.skills import SkillCatalog

        # Monkey-patch catalog root via bind path: GoalEngine uses SkillCatalog()
        # default root; instead inject via plan_goal skill_context by binding
        # after we point SkillCatalog — use engine.bind_skills with custom catalog
        # by temporarily writing into a work root and patching enable/compose.
        store = GoalStore(root / "goal")
        engine = GoalEngine(
            store,
            runner_factory=lambda d: LiveStepRunner(d, allow_net=False),
        )
        # Direct skill_context via planner for unit isolation when vendor absent:
        from octop.contrib.workbuddy.goal.planner import plan_goal

        plan = plan_goal("写入 skill-out.md", skill_context="## Bound Skills\n\nSkill: handoff\nPass context")
        write = next(s for s in plan.steps if s.kind == "write")
        assert "handoff" in write.instruction.lower() or "Bound Skills" in write.instruction

        # Runtime bind path: install fake skills under catalog by constructing
        # SkillRuntime-compatible tree and overriding catalog in engine helpers.
        cat = SkillCatalog(skills)
        assert cat.scan() == 1
        engine.skill_ids = ["handoff"]
        engine.skills_work_root = root / "skillhub"

        # Patch SkillCatalog default by injecting through bind_skills after
        # temporarily replacing GoalEngine._skill_context:
        def _ctx() -> str:
            from octop.contrib.workbuddy.skills import SkillRuntime

            rt = SkillRuntime(cat, work_root=engine.skills_work_root or root / "skillhub")
            rt.enable("handoff")
            return rt.compose_system(["handoff"], max_chars=2000)

        engine._skill_context = _ctx  # type: ignore[method-assign]
        planned = engine.plan("写入 bind-out.md")
        w = next(s for s in planned.steps if s.kind == "write")
        assert "handoff" in w.instruction.lower() or "Pass context" in w.instruction


def main() -> int:
    tests = [
        ("plan_write_message", test_plan_write_and_message),
        ("llm_polish", test_llm_polish_keeps_structure),
        ("acceptor", test_acceptor_file_and_outbox),
        ("engine_accept", test_engine_accepts_demo_goal),
        ("engine_no_approve", test_engine_rejects_without_approval),
        ("engine_bind_skills", test_engine_bind_skills),
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
