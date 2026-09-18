# SPDX-License-Identifier: MIT
"""Channel inbound → create Task (Feishu / DingTalk / WeCom).

Contract-facing path: one IM message becomes one console task.
Outbound credentials remain env-based; this module only handles *inbound ingest*.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .task import TaskStore


_CHANNEL_ALIASES = {
    "feishu": "feishu",
    "lark": "feishu",
    "dingtalk": "dingtalk",
    "ding": "dingtalk",
    "wecom": "wecom",
    "wechat_work": "wecom",
    "wxwork": "wecom",
}


@dataclass
class InboundMessage:
    channel: str
    text: str
    sender: str = ""
    chat_id: str = ""
    message_id: str = ""
    raw: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "channel": self.channel,
            "text": self.text,
            "sender": self.sender,
            "chat_id": self.chat_id,
            "message_id": self.message_id,
        }


def normalize_channel(name: str) -> str:
    key = (name or "").strip().lower()
    return _CHANNEL_ALIASES.get(key, key)


def parse_inbound_body(body: dict[str, Any]) -> InboundMessage:
    """Accept a normalized body or a light Feishu/DingTalk/WeCom webhook shape."""
    channel = normalize_channel(str(body.get("channel") or body.get("provider") or ""))
    text = str(body.get("text") or body.get("content") or body.get("message") or "").strip()
    sender = str(body.get("sender") or body.get("from") or body.get("user_id") or "").strip()
    chat_id = str(body.get("chat_id") or body.get("conversation_id") or "").strip()
    message_id = str(body.get("message_id") or body.get("msgid") or "").strip()

    # Feishu event envelope (simplified)
    event = body.get("event") if isinstance(body.get("event"), dict) else None
    if event and not text:
        msg = event.get("message") if isinstance(event.get("message"), dict) else {}
        content = msg.get("content")
        if isinstance(content, str):
            # often JSON string {"text":"..."}
            try:
                import json as _json

                parsed = _json.loads(content)
                if isinstance(parsed, dict) and parsed.get("text"):
                    text = str(parsed["text"])
                else:
                    text = content
            except Exception:
                m = re.search(r'"text"\s*:\s*"([^"]*)"', content)
                text = m.group(1) if m else content
        sender = sender or str((event.get("sender") or {}).get("sender_id", {}).get("user_id") or "")
        chat_id = chat_id or str(msg.get("chat_id") or "")
        message_id = message_id or str(msg.get("message_id") or "")
        channel = channel or "feishu"

    # DingTalk text robot
    if not text and isinstance(body.get("text"), dict):
        text = str(body["text"].get("content") or "").strip()
        channel = channel or "dingtalk"
        sender = sender or str((body.get("senderStaffId") or body.get("senderNick") or ""))

    # WeCom text
    if not text and body.get("MsgType") == "text":
        text = str(body.get("Content") or "").strip()
        channel = channel or "wecom"
        sender = sender or str(body.get("FromUserName") or "")

    if not channel:
        channel = "feishu"
    if not text:
        raise ValueError("inbound text required")
    return InboundMessage(
        channel=channel,
        text=text,
        sender=sender,
        chat_id=chat_id,
        message_id=message_id,
        raw=body,
    )


def ingest_to_task(
    msg: InboundMessage,
    *,
    tasks_root: Path | str,
    mode: str = "craft",
    project_id: str = "",
    title_prefix: str = "",
) -> dict[str, Any]:
    store = TaskStore(tasks_root)
    prefix = title_prefix or f"[{msg.channel}]"
    title = f"{prefix} {(msg.text[:36] or 'inbound').strip()}"
    prompt = (
        f"来自通道 {msg.channel}\n"
        f"发送者：{msg.sender or 'unknown'}\n"
        f"会话：{msg.chat_id or '-'}\n"
        f"消息ID：{msg.message_id or '-'}\n\n"
        f"{msg.text}"
    )
    rec = store.create(title=title, mode=mode, prompt=prompt, project_id=project_id)
    store.append_message(rec.task_id, "user", msg.text)
    store.append_message(
        rec.task_id,
        "system",
        f"通道入站已建任务（{msg.channel}）" + (f"；sender={msg.sender}" if msg.sender else ""),
    )
    store.add_result(
        rec.task_id,
        {"kind": "channel_inbound", **msg.to_dict()},
    )
    return {
        "ok": True,
        "task_id": rec.task_id,
        "task": rec.to_dict(),
        "inbound": msg.to_dict(),
    }
