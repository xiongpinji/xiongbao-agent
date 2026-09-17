# SPDX-License-Identifier: MIT
"""Tests for Routine cron matcher + tick scheduler."""

from __future__ import annotations

import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT))

from octop.contrib.workbuddy.routine import (  # noqa: E402
    RoutineEngine,
    RoutineScheduler,
    RoutineStore,
    is_due,
    matches_cron,
    next_match,
)
from octop.contrib.workbuddy.routine.cron import resolve_tz  # noqa: E402
from octop.contrib.workbuddy.teach import (  # noqa: E402
    TeachRecorder,
    TeachStore,
    draft_skill_from_recording,
)


def test_matches_cron_basic() -> None:
    when = datetime(2026, 9, 18, 9, 0, tzinfo=resolve_tz("Asia/Shanghai"))
    assert matches_cron("0 9 * * *", when)
    assert not matches_cron("0 10 * * *", when)
    assert matches_cron("*/15 * * * *", when.replace(minute=30))
    assert matches_cron("0 9 * * 5", when)  # 2026-09-18 is Friday → cron dow 5


def test_is_due_respects_last_fired() -> None:
    tz = "Asia/Shanghai"
    slot = datetime(2026, 9, 18, 9, 0, tzinfo=resolve_tz(tz))
    now_utc = slot.astimezone(timezone.utc)
    assert is_due("0 9 * * *", tz_name=tz, last_fired_at=None, now=now_utc)
    # already fired this minute
    assert not is_due(
        "0 9 * * *",
        tz_name=tz,
        last_fired_at=now_utc.isoformat(),
        now=now_utc,
    )
    # fired yesterday → due again
    yesterday = (now_utc - timedelta(days=1)).isoformat()
    assert is_due("0 9 * * *", tz_name=tz, last_fired_at=yesterday, now=now_utc)


def test_next_match_finds_morning() -> None:
    tz = "Asia/Shanghai"
    after = datetime(2026, 9, 18, 8, 30, tzinfo=resolve_tz(tz))
    nxt = next_match("0 9 * * *", tz_name=tz, after=after.astimezone(timezone.utc))
    assert nxt is not None
    assert nxt.hour == 9 and nxt.minute == 0


def test_scheduler_tick_once_per_slot() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        teach = TeachStore(root / "teach")
        routines = RoutineStore(root / "routines")

        rec = TeachRecorder(bot_id="b1", intent="定时汇总")
        rec.read_data("src")
        draft = draft_skill_from_recording(rec.close(), name="daily-summary")
        teach.save_draft(draft)
        draft = teach.approve_draft(draft.name)

        engine = RoutineEngine(routines)
        routine = engine.create_from_draft(
            draft, bot_id="b1", cron="0 9 * * *", timezone="Asia/Shanghai"
        )
        # simulate created earlier so current slot can fire
        routine.created_at = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
        routine.last_fired_at = None
        routines.save(routine)

        slot = datetime(2026, 9, 18, 9, 0, tzinfo=resolve_tz("Asia/Shanghai"))
        now = slot.astimezone(timezone.utc)
        sched = RoutineScheduler(routines, teach, engine)

        due = sched.list_due(now=now)
        assert len(due) == 1

        first = sched.tick(mode="dry", now=now)
        assert len(first) == 1 and first[0].fired and first[0].run and first[0].run.ok

        # second tick same minute must not re-fire
        second = sched.tick(mode="dry", now=now)
        assert second == []

        loaded = routines.load(routine.id)
        assert loaded.last_fired_at
        assert len(loaded.last_runs) == 1


if __name__ == "__main__":
    test_matches_cron_basic()
    test_is_due_respects_last_fired()
    test_next_match_finds_morning()
    test_scheduler_tick_once_per_slot()
    # keep legacy suite green when run together
    from test_teach_routine import (  # noqa: E402
        test_bot_routine_limit,
        test_record_draft_approve_routine_dry,
        test_test_run_requires_confirm,
    )

    test_record_draft_approve_routine_dry()
    test_test_run_requires_confirm()
    test_bot_routine_limit()
    print("ALL SCHEDULER TESTS OK")
