# SPDX-License-Identifier: MIT
"""Minimal connectors for WorkBuddy parity (stdlib HTTP).

Credentials via env (never commit secrets)::

    WB_NOTION_TOKEN          Notion internal integration secret
    WB_FEISHU_WEBHOOK        Feishu/Lark custom bot webhook URL
    WB_FEISHU_APP_ID         (optional) open-platform app
    WB_FEISHU_APP_SECRET     (optional)
    WB_ALLOW_OUTBOUND=1      Required to actually POST messages (safety gate)

Targets use prefixes::

    notion:page/<page_id>
    notion:https://www.notion.so/...
    feishu:webhook
    feishu:webhook/<alias>   (alias ignored; uses WB_FEISHU_WEBHOOK)
"""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse


class ConnectorError(RuntimeError):
    pass


def _env(name: str, default: str = "") -> str:
    return (os.environ.get(name) or default).strip()


def outbound_allowed() -> bool:
    return _env("WB_ALLOW_OUTBOUND") in {"1", "true", "yes", "on"}


@dataclass
class ConnectorResult:
    ok: bool
    provider: str
    action: str
    data: dict[str, Any]
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "provider": self.provider,
            "action": self.action,
            "data": self.data,
            "error": self.error,
        }


def _http_json(
    method: str,
    url: str,
    *,
    headers: dict[str, str] | None = None,
    body: dict[str, Any] | None = None,
    timeout: float = 20.0,
) -> dict[str, Any]:
    data = None if body is None else json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("User-Agent", "xiongbao-connectors/1")
    if body is not None:
        req.add_header("Content-Type", "application/json; charset=utf-8")
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            if not raw.strip():
                return {"status": getattr(resp, "status", 200)}
            return json.loads(raw)
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:500]
        raise ConnectorError(f"HTTP {exc.code} {url}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise ConnectorError(f"network error: {exc.reason}") from exc


# --- Notion -----------------------------------------------------------------

_NOTION_UUID = re.compile(
    r"([0-9a-fA-F]{8}-?[0-9a-fA-F]{4}-?[0-9a-fA-F]{4}-?[0-9a-fA-F]{4}-?[0-9a-fA-F]{12})"
)


def parse_notion_page_id(target: str) -> str:
    """Extract Notion page id from ``notion:page/<id>`` or a Notion URL."""
    t = target.strip()
    if t.lower().startswith("notion:"):
        t = t[7:]
    if t.lower().startswith("page/"):
        t = t[5:]
    m = _NOTION_UUID.search(t)
    if not m:
        raise ConnectorError(f"cannot parse Notion page id from: {target}")
    raw = m.group(1).replace("-", "")
    if len(raw) != 32:
        raise ConnectorError(f"invalid Notion page id length from: {target}")
    return f"{raw[0:8]}-{raw[8:12]}-{raw[12:16]}-{raw[16:20]}-{raw[20:32]}"


class NotionConnector:
    """Read-only Notion REST client (pages + block children)."""

    def __init__(self, token: str | None = None, *, timeout: float = 20.0) -> None:
        self.token = token if token is not None else _env("WB_NOTION_TOKEN")
        self.timeout = timeout
        self.version = "2022-06-28"

    def configured(self) -> bool:
        return bool(self.token)

    def _headers(self) -> dict[str, str]:
        if not self.token:
            raise ConnectorError("WB_NOTION_TOKEN not set")
        return {
            "Authorization": f"Bearer {self.token}",
            "Notion-Version": self.version,
        }

    def get_page(self, page_id: str) -> ConnectorResult:
        url = f"https://api.notion.com/v1/pages/{page_id}"
        try:
            data = _http_json("GET", url, headers=self._headers(), timeout=self.timeout)
            return ConnectorResult(True, "notion", "get_page", {"page": data, "page_id": page_id})
        except ConnectorError as exc:
            return ConnectorResult(False, "notion", "get_page", {"page_id": page_id}, str(exc))

    def list_block_children(self, block_id: str, *, page_size: int = 20) -> ConnectorResult:
        url = f"https://api.notion.com/v1/blocks/{block_id}/children?page_size={page_size}"
        try:
            data = _http_json("GET", url, headers=self._headers(), timeout=self.timeout)
            results = data.get("results") if isinstance(data, dict) else []
            texts: list[str] = []
            for block in results or []:
                if not isinstance(block, dict):
                    continue
                btype = str(block.get("type") or "")
                payload = block.get(btype) or {}
                rich = payload.get("rich_text") or payload.get("text") or []
                if isinstance(rich, list):
                    texts.append("".join(str(x.get("plain_text") or "") for x in rich if isinstance(x, dict)))
            return ConnectorResult(
                True,
                "notion",
                "list_blocks",
                {"block_id": block_id, "count": len(results or []), "preview": texts[:10]},
            )
        except ConnectorError as exc:
            return ConnectorResult(False, "notion", "list_blocks", {"block_id": block_id}, str(exc))

    def read_target(self, target: str) -> ConnectorResult:
        page_id = parse_notion_page_id(target)
        page = self.get_page(page_id)
        if not page.ok:
            return page
        blocks = self.list_block_children(page_id)
        return ConnectorResult(
            blocks.ok,
            "notion",
            "read",
            {"page_id": page_id, "page": page.data.get("page"), "blocks": blocks.data},
            blocks.error,
        )


# --- Feishu -----------------------------------------------------------------


class FeishuConnector:
    """Outbound Feishu via custom-bot webhook (default) or open API token."""

    def __init__(
        self,
        webhook: str | None = None,
        *,
        app_id: str | None = None,
        app_secret: str | None = None,
        timeout: float = 20.0,
    ) -> None:
        self.webhook = webhook if webhook is not None else _env("WB_FEISHU_WEBHOOK")
        self.app_id = app_id if app_id is not None else _env("WB_FEISHU_APP_ID")
        self.app_secret = app_secret if app_secret is not None else _env("WB_FEISHU_APP_SECRET")
        self.timeout = timeout

    def configured(self) -> bool:
        return bool(self.webhook) or (bool(self.app_id) and bool(self.app_secret))

    def send_text(self, text: str, *, require_outbound_flag: bool = True) -> ConnectorResult:
        if require_outbound_flag and not outbound_allowed():
            return ConnectorResult(
                False,
                "feishu",
                "send_text",
                {"queued_only": True, "text": text[:200]},
                "WB_ALLOW_OUTBOUND not set — message kept local",
            )
        if self.webhook:
            return self._send_webhook(text)
        if self.app_id and self.app_secret:
            return ConnectorResult(
                False,
                "feishu",
                "send_text",
                {},
                "open-platform chat send not configured; set WB_FEISHU_WEBHOOK for MVP",
            )
        return ConnectorResult(False, "feishu", "send_text", {}, "WB_FEISHU_WEBHOOK not set")

    def _send_webhook(self, text: str) -> ConnectorResult:
        url = self.webhook
        parsed = urlparse(url or "")
        if parsed.scheme not in {"http", "https"}:
            return ConnectorResult(False, "feishu", "webhook", {}, "invalid webhook URL")
        body = {"msg_type": "text", "content": {"text": text}}
        try:
            data = _http_json("POST", url, body=body, timeout=self.timeout)
            # Feishu returns {code:0} or {StatusCode:0}
            code = data.get("code", data.get("StatusCode", 0))
            ok = code in (0, "0", None) or data.get("StatusMessage") == "success"
            return ConnectorResult(bool(ok), "feishu", "webhook", {"response": data, "chars": len(text)}, None if ok else str(data))
        except ConnectorError as exc:
            return ConnectorResult(False, "feishu", "webhook", {}, str(exc))


def resolve_read(target: str, *, notion: NotionConnector | None = None) -> ConnectorResult | None:
    """If target is a Notion URI, fetch it; else return None (caller handles locally)."""
    t = target.strip().lower()
    if t.startswith("notion:") or "notion.so" in target:
        client = notion or NotionConnector()
        if not client.configured():
            return ConnectorResult(False, "notion", "read", {"target": target}, "WB_NOTION_TOKEN not set")
        return client.read_target(target)
    return None


def resolve_message(
    target: str,
    text: str,
    *,
    feishu: FeishuConnector | None = None,
    require_outbound_flag: bool = True,
) -> ConnectorResult | None:
    """If target is Feishu, send (or refuse without outbound flag); else None."""
    t = target.strip().lower()
    if t.startswith("feishu:") or t.startswith("lark:"):
        client = feishu or FeishuConnector()
        return client.send_text(text, require_outbound_flag=require_outbound_flag)
    return None


def probe_status() -> dict[str, Any]:
    notion = NotionConnector()
    feishu = FeishuConnector()
    return {
        "notion": {"configured": notion.configured(), "token_set": bool(notion.token)},
        "feishu": {
            "configured": feishu.configured(),
            "webhook_set": bool(feishu.webhook),
            "app_set": bool(feishu.app_id and feishu.app_secret),
        },
        "outbound_allowed": outbound_allowed(),
    }
