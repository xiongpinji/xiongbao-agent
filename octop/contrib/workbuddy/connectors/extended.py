# SPDX-License-Identifier: MIT
"""DingTalk / WeCom outbound webhooks + connector catalog from vendor archive."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from . import ConnectorError, ConnectorResult, _env, _http_json, outbound_allowed


def default_connectors_root(project_root: Path | None = None) -> Path:
    root = project_root or Path(__file__).resolve().parents[4]
    return root / "vendor" / "workbuddyskills" / "connectors"


@dataclass
class ConnectorPackageMeta:
    id: str
    path: str
    has_mcp: bool
    has_cli: bool
    has_skills: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "path": self.path,
            "has_mcp": self.has_mcp,
            "has_cli": self.has_cli,
            "has_skills": self.has_skills,
        }


class ConnectorCatalog:
    """Index ``vendor/workbuddyskills/connectors/*`` packages (metadata only)."""

    def __init__(self, root: Path | None = None) -> None:
        self.root = Path(root) if root else default_connectors_root()
        self._items: list[ConnectorPackageMeta] = []
        self._scanned = False

    def scan(self, *, force: bool = False) -> int:
        if self._scanned and not force:
            return len(self._items)
        items: list[ConnectorPackageMeta] = []
        if self.root.is_dir():
            for d in sorted(self.root.iterdir()):
                if not d.is_dir():
                    continue
                items.append(
                    ConnectorPackageMeta(
                        id=d.name,
                        path=str(d),
                        has_mcp=(d / "mcp.json").is_file(),
                        has_cli=(d / "cli.json").is_file(),
                        has_skills=(d / "skills").is_dir(),
                    )
                )
        self._items = items
        self._scanned = True
        return len(items)

    def list(self) -> list[ConnectorPackageMeta]:
        self.scan()
        return list(self._items)

    def search(self, query: str, *, limit: int = 30) -> list[ConnectorPackageMeta]:
        self.scan()
        q = (query or "").strip().lower()
        if not q:
            return self._items[:limit]
        return [c for c in self._items if q in c.id.lower()][:limit]


class DingTalkConnector:
    """Custom robot webhook (text). Env: ``WB_DINGTALK_WEBHOOK``."""

    def __init__(self, webhook: str | None = None, *, timeout: float = 20.0) -> None:
        self.webhook = webhook if webhook is not None else _env("WB_DINGTALK_WEBHOOK")
        self.timeout = timeout

    def configured(self) -> bool:
        return bool(self.webhook)

    def send_text(self, text: str, *, require_outbound_flag: bool = True) -> ConnectorResult:
        if require_outbound_flag and not outbound_allowed():
            return ConnectorResult(
                False,
                "dingtalk",
                "send_text",
                {"queued_only": True, "text": text[:200]},
                "WB_ALLOW_OUTBOUND not set — message kept local",
            )
        if not self.webhook:
            return ConnectorResult(False, "dingtalk", "send_text", {}, "WB_DINGTALK_WEBHOOK not set")
        parsed = urlparse(self.webhook)
        if parsed.scheme not in {"http", "https"}:
            return ConnectorResult(False, "dingtalk", "send_text", {}, "invalid webhook URL")
        body = {"msgtype": "text", "text": {"content": text}}
        try:
            data = _http_json("POST", self.webhook, body=body, timeout=self.timeout)
            errcode = data.get("errcode", data.get("code", 0))
            ok = errcode in (0, "0", None)
            return ConnectorResult(
                bool(ok),
                "dingtalk",
                "webhook",
                {"response": data, "chars": len(text)},
                None if ok else str(data),
            )
        except ConnectorError as exc:
            return ConnectorResult(False, "dingtalk", "webhook", {}, str(exc))


class WeComConnector:
    """WeCom group robot webhook. Env: ``WB_WECOM_WEBHOOK``."""

    def __init__(self, webhook: str | None = None, *, timeout: float = 20.0) -> None:
        self.webhook = webhook if webhook is not None else _env("WB_WECOM_WEBHOOK")
        self.timeout = timeout

    def configured(self) -> bool:
        return bool(self.webhook)

    def send_text(self, text: str, *, require_outbound_flag: bool = True) -> ConnectorResult:
        if require_outbound_flag and not outbound_allowed():
            return ConnectorResult(
                False,
                "wecom",
                "send_text",
                {"queued_only": True, "text": text[:200]},
                "WB_ALLOW_OUTBOUND not set — message kept local",
            )
        if not self.webhook:
            return ConnectorResult(False, "wecom", "send_text", {}, "WB_WECOM_WEBHOOK not set")
        parsed = urlparse(self.webhook)
        if parsed.scheme not in {"http", "https"}:
            return ConnectorResult(False, "wecom", "send_text", {}, "invalid webhook URL")
        body = {"msgtype": "text", "text": {"content": text}}
        try:
            data = _http_json("POST", self.webhook, body=body, timeout=self.timeout)
            errcode = data.get("errcode", data.get("code", 0))
            ok = errcode in (0, "0", None)
            return ConnectorResult(
                bool(ok),
                "wecom",
                "webhook",
                {"response": data, "chars": len(text)},
                None if ok else str(data),
            )
        except ConnectorError as exc:
            return ConnectorResult(False, "wecom", "webhook", {}, str(exc))


def resolve_message_extended(
    target: str,
    text: str,
    *,
    require_outbound_flag: bool = True,
) -> ConnectorResult | None:
    """Handle ``dingtalk:`` / ``wecom:`` / ``wechatwork:`` targets."""
    t = target.strip().lower()
    if t.startswith("dingtalk:"):
        return DingTalkConnector().send_text(text, require_outbound_flag=require_outbound_flag)
    if t.startswith("wecom:") or t.startswith("wechatwork:") or t.startswith("wxwork:"):
        return WeComConnector().send_text(text, require_outbound_flag=require_outbound_flag)
    return None


def probe_extended_status() -> dict[str, Any]:
    ding = DingTalkConnector()
    wecom = WeComConnector()
    cat = ConnectorCatalog()
    n = cat.scan()
    return {
        "dingtalk": {"configured": ding.configured()},
        "wecom": {"configured": wecom.configured()},
        "catalog": {"root": str(cat.root), "count": n},
        "outbound_allowed": outbound_allowed(),
        "env_hints": {
            "WB_DINGTALK_WEBHOOK": bool(os.environ.get("WB_DINGTALK_WEBHOOK")),
            "WB_WECOM_WEBHOOK": bool(os.environ.get("WB_WECOM_WEBHOOK")),
        },
    }


def load_mcp_json(connector_id: str, *, root: Path | None = None) -> dict[str, Any] | None:
    """Read mcp.json for a vendor connector package (no secrets required)."""
    base = Path(root) if root else default_connectors_root()
    path = base / connector_id / "mcp.json"
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None
