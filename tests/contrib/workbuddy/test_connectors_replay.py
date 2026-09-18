# SPDX-License-Identifier: MIT
"""Tests for connectors + CDP replay (no live Chrome/API required)."""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any
from unittest.mock import patch

PROJECT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT))

from octop.contrib.workbuddy.connectors import (  # noqa: E402
    ConnectorError,
    FeishuConnector,
    NotionConnector,
    parse_feishu_target,
    parse_notion_page_id,
    probe_status,
)
from octop.contrib.workbuddy.routine.live_runner import LiveStepRunner  # noqa: E402
from octop.contrib.workbuddy.teach.cdp_client import CdpClient  # noqa: E402
from octop.contrib.workbuddy.teach.cdp_replay import CdpReplaySession  # noqa: E402
from octop.contrib.workbuddy.teach.models import DraftStep  # noqa: E402


def test_parse_notion_page_id() -> None:
    pid = "a1b2c3d4e5f6789012345678abcdef01"
    dashed = "a1b2c3d4-e5f6-7890-1234-5678abcdef01"
    assert parse_notion_page_id(f"notion:page/{dashed}") == dashed
    assert parse_notion_page_id(f"https://www.notion.so/My-Page-{pid}") == dashed
    try:
        parse_notion_page_id("notion:page/not-an-id")
        raise AssertionError("expected error")
    except ConnectorError:
        pass


def test_parse_feishu_target() -> None:
    assert parse_feishu_target("feishu:webhook")["mode"] == "webhook"
    assert parse_feishu_target("feishu:chat/oc_abc") == {
        "mode": "open",
        "receive_id": "oc_abc",
        "receive_id_type": "chat_id",
    }
    assert parse_feishu_target("lark:open_id/ou_1")["receive_id_type"] == "open_id"
    assert parse_feishu_target("feishu:open")["mode"] == "open"


def test_probe_status_no_env() -> None:
    with patch.dict(os.environ, {}, clear=False):
        for key in (
            "WB_NOTION_TOKEN",
            "WB_FEISHU_WEBHOOK",
            "WB_FEISHU_APP_ID",
            "WB_FEISHU_APP_SECRET",
            "WB_FEISHU_RECEIVE_ID",
            "WB_ALLOW_OUTBOUND",
        ):
            os.environ.pop(key, None)
        st = probe_status()
        assert st["notion"]["configured"] is False
        assert st["feishu"]["configured"] is False
        assert st["feishu"]["open_api_ready"] is False
        assert st["outbound_allowed"] is False


def test_feishu_blocks_without_outbound_flag() -> None:
    with patch.dict(os.environ, {"WB_FEISHU_WEBHOOK": "https://open.feishu.cn/hook/x"}, clear=False):
        os.environ.pop("WB_ALLOW_OUTBOUND", None)
        fc = FeishuConnector()
        res = fc.send_text("hi", require_outbound_flag=True)
        assert not res.ok
        assert "WB_ALLOW_OUTBOUND" in (res.error or "")


def test_feishu_webhook_post() -> None:
    calls: list[tuple[str, str, Any]] = []

    def fake_http(method: str, url: str, *, headers=None, body=None, timeout=20.0):
        calls.append((method, url, body))
        return {"code": 0, "msg": "success"}

    with patch.dict(
        os.environ,
        {"WB_FEISHU_WEBHOOK": "https://open.feishu.cn/open-apis/bot/v2/hook/test", "WB_ALLOW_OUTBOUND": "1"},
        clear=False,
    ):
        with patch("octop.contrib.workbuddy.connectors._http_json", side_effect=fake_http):
            fc = FeishuConnector()
            res = fc.send_text("hello feishu", require_outbound_flag=True)
        assert res.ok
        assert calls and calls[0][0] == "POST"
        assert calls[0][2]["msg_type"] == "text"


def test_feishu_open_api_post() -> None:
    calls: list[dict[str, Any]] = []

    def fake_http(method: str, url: str, *, headers=None, body=None, timeout=20.0):
        calls.append({"method": method, "url": url, "headers": headers or {}, "body": body})
        if "tenant_access_token" in url:
            return {"code": 0, "tenant_access_token": "t-test-token", "expire": 7200}
        if "/im/v1/messages" in url:
            assert headers and headers.get("Authorization") == "Bearer t-test-token"
            assert "receive_id_type=chat_id" in url
            assert body["receive_id"] == "oc_demo"
            assert body["msg_type"] == "text"
            assert json.loads(body["content"])["text"] == "open api hi"
            return {"code": 0, "data": {"message_id": "om_1"}}
        raise AssertionError(url)

    env = {
        "WB_FEISHU_APP_ID": "cli_demo",
        "WB_FEISHU_APP_SECRET": "sec_demo",
        "WB_FEISHU_RECEIVE_ID": "oc_env_default",
        "WB_ALLOW_OUTBOUND": "1",
    }
    # Prefer open target even if webhook also set
    env["WB_FEISHU_WEBHOOK"] = "https://open.feishu.cn/open-apis/bot/v2/hook/ignored"
    with patch.dict(os.environ, env, clear=False):
        with patch("octop.contrib.workbuddy.connectors._http_json", side_effect=fake_http):
            fc = FeishuConnector()
            res = fc.send_text(
                "open api hi",
                require_outbound_flag=True,
                target="feishu:chat/oc_demo",
            )
    assert res.ok, res.error
    assert res.action == "open_api"
    assert any("tenant_access_token" in c["url"] for c in calls)
    assert any("/im/v1/messages" in c["url"] for c in calls)


def test_notion_read_mocked() -> None:
    def fake_http(method: str, url: str, *, headers=None, body=None, timeout=20.0):
        if "/pages/" in url:
            return {"id": "a1b2c3d4-e5f6-7890-1234-5678abcdef01", "object": "page"}
        if "/blocks/" in url:
            return {
                "results": [
                    {
                        "type": "paragraph",
                        "paragraph": {"rich_text": [{"plain_text": "PR list"}]},
                    }
                ]
            }
        raise AssertionError(url)

    with patch.dict(os.environ, {"WB_NOTION_TOKEN": "secret"}, clear=False):
        with patch("octop.contrib.workbuddy.connectors._http_json", side_effect=fake_http):
            nc = NotionConnector()
            res = nc.read_target("notion:page/a1b2c3d4-e5f6-7890-1234-5678abcdef01")
        assert res.ok
        assert res.data["blocks"]["preview"] == ["PR list"]


class _FakeReplay:
    def __init__(self) -> None:
        self.actions: list[tuple[str, Any]] = []

    def click(self, selector: str) -> dict[str, Any]:
        self.actions.append(("click", selector))
        return {"ok": True, "selector": selector}

    def type_text(self, selector: str, text: str) -> dict[str, Any]:
        self.actions.append(("type", selector, text))
        return {"ok": True, "selector": selector, "chars": len(text)}

    def navigate(self, url: str) -> dict[str, Any]:
        self.actions.append(("navigate", url))
        return {"ok": True, "url": url}


def test_live_runner_cdp_replay_and_feishu_skip() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        fake = _FakeReplay()
        runner = LiveStepRunner(Path(tmp), allow_net=False, cdp_replay=fake, allow_outbound=False)
        r1 = runner(
            DraftStep(0, "click", "点击（目标：#go）"),
            context={"mode": "test"},
        )
        assert r1["ok"]
        r2 = runner(
            DraftStep(1, "type", "输入（目标：#q）（内容：hi）"),
            context={"mode": "test"},
        )
        assert r2["ok"]
        r3 = runner(
            DraftStep(2, "message", "通知（目标：feishu:webhook）（内容：ping）"),
            context={"mode": "test"},
        )
        assert r3["ok"]
        assert r3["output"]["connector"]["skipped"] is True
        assert fake.actions[0][0] == "click"
        assert fake.actions[1][0] == "type"


def test_cdp_replay_session_with_fake_transport() -> None:
    class FakeTransport:
        def __init__(self) -> None:
            self._replies: list[str] = []
            self.sent: list[dict[str, Any]] = []

        def send_text(self, text: str) -> None:
            msg = json.loads(text)
            self.sent.append(msg)
            mid = msg["id"]
            expr = str(msg.get("params", {}).get("expression", ""))
            if "querySelector" in expr and "MouseEvent" in expr:
                val = {"ok": True, "selector": "#x", "tag": "BUTTON"}
            elif "querySelector" in expr and "HTMLInputElement" in expr:
                val = {"ok": True, "selector": "#q", "chars": 2}
            else:
                val = "ok"
            self._replies.append(json.dumps({"id": mid, "result": {"result": {"value": val}}}))

        def recv_text(self, *, timeout: float | None = None) -> str:
            return self._replies.pop(0)

        def close(self) -> None:
            pass

    tr = FakeTransport()
    session = CdpReplaySession(CdpClient(tr))
    assert session.click("#x")["ok"]
    assert session.type_text("#q", "hi")["ok"]


def main() -> int:
    tests = [
        ("parse_notion_page_id", test_parse_notion_page_id),
        ("parse_feishu_target", test_parse_feishu_target),
        ("probe_status", test_probe_status_no_env),
        ("feishu_blocks", test_feishu_blocks_without_outbound_flag),
        ("feishu_webhook", test_feishu_webhook_post),
        ("feishu_open_api", test_feishu_open_api_post),
        ("notion_read", test_notion_read_mocked),
        ("live_cdp_feishu", test_live_runner_cdp_replay_and_feishu_skip),
        ("cdp_replay_session", test_cdp_replay_session_with_fake_transport),
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
    print("ALL CONNECTOR/REPLAY TESTS OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
