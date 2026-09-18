# SPDX-License-Identifier: MIT
"""WeChat / QQ messaging connectors (webhook outbound + inbox JSONL inbound)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from . import ConnectorError, ConnectorResult, _env, _http_json, outbound_allowed


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


class InboxStore:
    """Append-only inbound message inbox (JSONL)."""

    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, provider: str, payload: dict[str, Any]) -> dict[str, Any]:
        record = {"ts": _utc(), "provider": provider, **payload}
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
        return record

    def read_tail(self, n: int = 20) -> list[dict[str, Any]]:
        if not self.path.is_file():
            return []
        lines = self.path.read_text(encoding="utf-8").splitlines()
        out: list[dict[str, Any]] = []
        for line in lines[-n:]:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return out


class WeChatConnector:
    """Enterprise WeChat / personal WeChat bot webhook style outbound.

    Env::
        WB_WECHAT_WEBHOOK
    """

    def __init__(self, webhook: str | None = None, *, timeout: float = 20.0) -> None:
        self.webhook = webhook if webhook is not None else _env("WB_WECHAT_WEBHOOK")
        self.timeout = timeout

    def configured(self) -> bool:
        return bool(self.webhook)

    def send_text(self, text: str, *, require_outbound_flag: bool = True) -> ConnectorResult:
        if require_outbound_flag and not outbound_allowed():
            return ConnectorResult(
                False,
                "wechat",
                "send_text",
                {"queued_only": True, "text": text[:200]},
                "WB_ALLOW_OUTBOUND not set — message kept local",
            )
        if not self.webhook:
            return ConnectorResult(False, "wechat", "send_text", {}, "WB_WECHAT_WEBHOOK not set")
        parsed = urlparse(self.webhook)
        if parsed.scheme not in {"http", "https"}:
            return ConnectorResult(False, "wechat", "send_text", {}, "invalid webhook URL")
        body = {"msgtype": "text", "text": {"content": text}}
        try:
            data = _http_json("POST", self.webhook, body=body, timeout=self.timeout)
            errcode = data.get("errcode", data.get("code", 0))
            ok = errcode in (0, "0", None)
            return ConnectorResult(
                bool(ok),
                "wechat",
                "send_text",
                {"response": data, "chars": len(text)},
                None if ok else str(data),
            )
        except ConnectorError as exc:
            return ConnectorResult(False, "wechat", "send_text", {}, str(exc))


class QQConnector:
    """QQ bot webhook outbound (OneBot-style JSON).

    Env::
        WB_QQ_WEBHOOK
    """

    def __init__(self, webhook: str | None = None, *, timeout: float = 20.0) -> None:
        self.webhook = webhook if webhook is not None else _env("WB_QQ_WEBHOOK")
        self.timeout = timeout

    def configured(self) -> bool:
        return bool(self.webhook)

    def send_text(
        self,
        text: str,
        *,
        user_id: str | None = None,
        group_id: str | None = None,
        require_outbound_flag: bool = True,
    ) -> ConnectorResult:
        if require_outbound_flag and not outbound_allowed():
            return ConnectorResult(
                False,
                "qq",
                "send_text",
                {"queued_only": True, "text": text[:200]},
                "WB_ALLOW_OUTBOUND not set — message kept local",
            )
        if not self.webhook:
            return ConnectorResult(False, "qq", "send_text", {}, "WB_QQ_WEBHOOK not set")
        parsed = urlparse(self.webhook)
        if parsed.scheme not in {"http", "https"}:
            return ConnectorResult(False, "qq", "send_text", {}, "invalid webhook URL")
        body: dict[str, Any] = {"message": text, "action": "send_msg"}
        if user_id:
            body["user_id"] = user_id
        if group_id:
            body["group_id"] = group_id
        try:
            data = _http_json("POST", self.webhook, body=body, timeout=self.timeout)
            return ConnectorResult(True, "qq", "send_text", {"response": data, "chars": len(text)})
        except ConnectorError as exc:
            return ConnectorResult(False, "qq", "send_text", {}, str(exc))


def probe_china_im_status() -> dict[str, Any]:
    wx = WeChatConnector()
    qq = QQConnector()
    return {
        "wechat": {"configured": wx.configured(), "webhook_set": bool(wx.webhook)},
        "qq": {"configured": qq.configured(), "webhook_set": bool(qq.webhook)},
    }


def resolve_message_china_im(
    target: str,
    text: str,
    *,
    require_outbound_flag: bool = True,
) -> ConnectorResult | None:
    t = target.strip().lower()
    if t.startswith("wechat:") or t.startswith("weixin:"):
        return WeChatConnector().send_text(text, require_outbound_flag=require_outbound_flag)
    if t.startswith("qq:"):
        rest = target.split(":", 1)[1].strip()
        user_id = None
        group_id = None
        if rest.startswith("user/"):
            user_id = rest[5:]
        elif rest.startswith("group/"):
            group_id = rest[6:]
        return QQConnector().send_text(
            text,
            user_id=user_id,
            group_id=group_id,
            require_outbound_flag=require_outbound_flag,
        )
    return None
