# SPDX-License-Identifier: MIT
"""Unit tests for CDP client/recorder and LiveStepRunner (no real Chrome required)."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from typing import Any

PROJECT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT))

from octop.contrib.workbuddy.routine import (  # noqa: E402
    LiveStepRunner,
    RoutineEngine,
    RoutineStore,
)
from octop.contrib.workbuddy.routine.live_runner import parse_target  # noqa: E402
from octop.contrib.workbuddy.teach import (  # noqa: E402
    TeachRecorder,
    TeachStore,
    draft_skill_from_recording,
)
from octop.contrib.workbuddy.teach.cdp_client import (  # noqa: E402
    CdpClient,
    CdpError,
    pick_page_ws_url,
)
from octop.contrib.workbuddy.teach.cdp_recorder import CdpTeachSession  # noqa: E402
from octop.contrib.workbuddy.teach.models import DraftStep  # noqa: E402


class FakeTransport:
    """Queue-based CDP transport for unit tests."""

    def __init__(self) -> None:
        self.sent: list[dict[str, Any]] = []
        self._replies: list[str] = []

    def queue_result(self, msg_id: int, result: Any) -> None:
        self._replies.append(json.dumps({"id": msg_id, "result": result}))

    def send_text(self, text: str) -> None:
        msg = json.loads(text)
        self.sent.append(msg)
        # Auto-ack with empty result unless pre-queued
        mid = msg["id"]
        # Prefer pre-queued replies that match id
        for i, raw in enumerate(self._replies):
            data = json.loads(raw)
            if data.get("id") == mid:
                return
        self._replies.append(json.dumps({"id": mid, "result": {}}))

    def recv_text(self, *, timeout: float | None = None) -> str:
        if not self._replies:
            raise TimeoutError("empty")
        return self._replies.pop(0)

    def close(self) -> None:
        pass


def test_pick_page_ws_url() -> None:
    targets = [
        {"type": "background_page", "webSocketDebuggerUrl": "ws://x/bg"},
        {
            "type": "page",
            "url": "https://example.com/a",
            "webSocketDebuggerUrl": "ws://x/a",
        },
        {
            "type": "page",
            "url": "https://notion.so/prs",
            "webSocketDebuggerUrl": "ws://x/notion",
        },
    ]
    assert pick_page_ws_url(targets) == "ws://x/a"
    assert pick_page_ws_url(targets, prefer_url="notion") == "ws://x/notion"
    try:
        pick_page_ws_url([])
        raise AssertionError("expected CdpError")
    except CdpError:
        pass


def test_cdp_client_call() -> None:
    tr = FakeTransport()
    client = CdpClient(tr)
    # Pre-queue matching reply for id=1
    tr._replies.clear()
    tr.queue_result(1, {"ok": True})
    # But send_text will also append — fix FakeTransport: don't auto-ack if already queued

    # Rebuild with smarter fake
    class SmartFake(FakeTransport):
        def send_text(self, text: str) -> None:
            msg = json.loads(text)
            self.sent.append(msg)
            mid = msg["id"]
            for raw in self._replies:
                if json.loads(raw).get("id") == mid:
                    return
            self._replies.append(json.dumps({"id": mid, "result": {"auto": True}}))

    tr2 = SmartFake()
    tr2.queue_result(1, {"value": 42})
    client2 = CdpClient(tr2)
    result = client2.call("Runtime.evaluate", {"expression": "1"})
    assert result == {"value": 42}
    assert tr2.sent[0]["method"] == "Runtime.evaluate"


def test_cdp_session_poll_maps_events() -> None:
    class EvalFake(FakeTransport):
        def send_text(self, text: str) -> None:
            msg = json.loads(text)
            self.sent.append(msg)
            mid = msg["id"]
            expr = str(msg.get("params", {}).get("expression", ""))
            if msg.get("method") == "Runtime.evaluate" and "window.__wbTeachQueue = []" in expr:
                events = [
                    {"kind": "click", "selector": "#btn", "text": "提交"},
                    {"kind": "type", "selector": "#q", "value": "hello"},
                    {"kind": "navigate", "url": "https://example.com/done", "summary": "done"},
                ]
                self._replies.append(
                    json.dumps({"id": mid, "result": {"result": {"value": events}}})
                )
            else:
                self._replies.append(json.dumps({"id": mid, "result": {"result": {"value": "ok"}}}))

    with tempfile.TemporaryDirectory() as tmp:
        rec = TeachRecorder(bot_id="t", intent="cdp test", store_dir=Path(tmp))
        fake = EvalFake()
        client = CdpClient(fake)
        session = CdpTeachSession(rec, client, poll_interval=0.01)
        n = session.poll_once()
        assert n == 3
        recording = rec.close()
        kinds = [s.kind for s in recording.steps]
        assert "click" in kinds
        assert "type" in kinds
        assert "navigate" in kinds


def test_parse_target() -> None:
    assert parse_target("打开页面（目标：https://a.com）") == "https://a.com"
    assert parse_target("no target") == ""


def test_live_runner_write_message_sandbox() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp) / "work"
        runner = LiveStepRunner(work, allow_net=False)
        step_w = DraftStep(
            index=0,
            kind="write",
            instruction="写入文件（目标：note.txt）（内容：hello live）",
        )
        r1 = runner(step_w, context={"mode": "live"})
        assert r1["ok"]
        assert (work / "files" / "note.txt").read_text(encoding="utf-8") == "hello live"

        step_m = DraftStep(
            index=1,
            kind="message",
            instruction="通知（目标：feishu:g1）",
            requires_approval=True,
        )
        r2 = runner(step_m, context={"mode": "live", "routine_id": "rt-1"})
        assert r2["ok"]
        outbox = work / "outbox" / "messages.jsonl"
        assert outbox.is_file()
        line = json.loads(outbox.read_text(encoding="utf-8").strip())
        assert line["target"] == "feishu:g1"

        bad = DraftStep(
            index=2,
            kind="write",
            instruction="坏路径（目标：../escape.txt）（内容：x）",
        )
        r3 = runner(bad, context={"mode": "live"})
        assert not r3["ok"]


def test_engine_with_live_runner() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        teach = TeachStore(root / "teach")
        routines = RoutineStore(root / "routines")
        rec = TeachRecorder(bot_id="b1", intent="写文件并通知")
        rec.append("write", "落盘", target="out.txt", value="ok")
        rec.append("message", "发消息", tool_name="send", target="local:outbox")
        draft = draft_skill_from_recording(rec.close(), name="live-write")
        teach.save_draft(draft)
        draft = teach.approve_draft("live-write")
        runner = LiveStepRunner(root / "live", allow_net=False)
        engine = RoutineEngine(routines, runner=runner)
        routine = engine.create_from_draft(draft, bot_id="b1", cron=None)
        approvals = {f"step:{s.index}" for s in draft.steps if s.requires_approval}
        for ap in draft.approvals:
            approvals.add(f"action:{ap.action}")
        run = engine.run(
            routine,
            draft,
            mode="test",
            confirm_test=True,
            approvals=approvals,
        )
        assert run.ok, run.error
        assert (root / "live" / "files" / "out.txt").read_text(encoding="utf-8") == "ok"


def main() -> int:
    tests = [
        ("pick_page_ws_url", test_pick_page_ws_url),
        ("cdp_client_call", test_cdp_client_call),
        ("cdp_session_poll", test_cdp_session_poll_maps_events),
        ("parse_target", test_parse_target),
        ("live_runner_sandbox", test_live_runner_write_message_sandbox),
        ("engine_live_runner", test_engine_with_live_runner),
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
    print("ALL CDP/LIVE TESTS OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
