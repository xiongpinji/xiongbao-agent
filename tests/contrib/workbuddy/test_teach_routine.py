# SPDX-License-Identifier: MIT
"""Tests for Teach recorder + Routine engine (V2)."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT))

from octop.contrib.workbuddy.routine import (  # noqa: E402
    RoutineEngine,
    RoutineStore,
    SafetyError,
)
from octop.contrib.workbuddy.teach import (  # noqa: E402
    TeachRecorder,
    TeachStore,
    draft_skill_from_recording,
)


def test_record_draft_approve_routine_dry() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        teach = TeachStore(root / "teach")
        routines = RoutineStore(root / "routines")

        rec = TeachRecorder(bot_id="b1", intent="抓取 PR 并发送飞书", store_dir=teach.recordings_dir)
        rec.navigate("https://notion.example/prs")
        rec.read_data("prs")
        rec.decision("列表非空？")
        rec.append("message", "发送摘要到飞书", tool_name="send", target="feishu:g1")
        recording = rec.close()
        teach.save_recording(recording)

        draft = draft_skill_from_recording(recording, name="pr-feishu")
        assert len(draft.steps) >= 4
        assert any(s.is_decision for s in draft.steps)
        assert draft.approvals, "expected approval boundaries"
        assert draft.status == "draft"
        teach.save_draft(draft)

        engine = RoutineEngine(routines)
        try:
            engine.create_from_draft(draft, bot_id="b1")
            raise AssertionError("should reject unapproved draft")
        except SafetyError:
            pass

        draft = teach.approve_draft("pr-feishu")
        routine = engine.create_from_draft(draft, bot_id="b1", cron="0 9 * * *")
        run = engine.run(routine, draft, mode="dry")
        assert run.ok
        assert len(run.step_results) == len(draft.steps)


def test_test_run_requires_confirm() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        teach = TeachStore(root / "teach")
        routines = RoutineStore(root / "routines")
        rec = TeachRecorder(bot_id="b1", intent="只读汇总")
        rec.read_data("src")
        recording = rec.close()
        draft = draft_skill_from_recording(recording, name="readonly")
        teach.save_draft(draft)
        draft = teach.approve_draft("readonly")
        engine = RoutineEngine(routines)
        routine = engine.create_from_draft(draft, bot_id="b1", cron=None)
        try:
            engine.run(routine, draft, mode="test", confirm_test=False)
            raise AssertionError("expected SafetyError")
        except SafetyError:
            pass
        run = engine.run(
            routine,
            draft,
            mode="test",
            confirm_test=True,
            approvals={f"step:{s.index}" for s in draft.steps if s.requires_approval},
        )
        assert run.ok


def test_bot_routine_limit() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        routines = RoutineStore(Path(tmp) / "routines")
        teach = TeachStore(Path(tmp) / "teach")
        engine = RoutineEngine(routines, max_per_bot=2)
        for i in range(2):
            rec = TeachRecorder(bot_id="b1", intent=f"task-{i}")
            rec.read_data(f"s{i}")
            draft = draft_skill_from_recording(rec.close(), name=f"sk-{i}")
            teach.save_draft(draft)
            draft = teach.approve_draft(draft.name)
            engine.create_from_draft(draft, bot_id="b1", cron=None)
        rec = TeachRecorder(bot_id="b1", intent="overflow")
        rec.read_data("x")
        draft = draft_skill_from_recording(rec.close(), name="sk-overflow")
        teach.save_draft(draft)
        draft = teach.approve_draft(draft.name)
        try:
            engine.create_from_draft(draft, bot_id="b1", cron=None)
            raise AssertionError("expected limit")
        except SafetyError:
            pass


if __name__ == "__main__":
    test_record_draft_approve_routine_dry()
    test_test_run_requires_confirm()
    test_bot_routine_limit()
    print("ALL TEACH/ROUTINE TESTS OK")
