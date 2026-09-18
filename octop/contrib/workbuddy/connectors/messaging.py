# SPDX-License-Identifier: MIT
"""Email (SMTP) + generic HTTP webhook connectors."""

from __future__ import annotations

import json
import smtplib
import ssl
import urllib.error
import urllib.request
from email.message import EmailMessage
from typing import Any
from urllib.parse import urlparse

from . import ConnectorError, ConnectorResult, _env, outbound_allowed


class EmailConnector:
    """SMTP outbound via env::

        WB_SMTP_HOST / WB_SMTP_PORT / WB_SMTP_USER / WB_SMTP_PASSWORD
        WB_SMTP_FROM / WB_SMTP_TLS (default 1)
    """

    def __init__(
        self,
        *,
        host: str | None = None,
        port: int | None = None,
        user: str | None = None,
        password: str | None = None,
        from_addr: str | None = None,
        use_tls: bool | None = None,
    ) -> None:
        self.host = (host if host is not None else _env("WB_SMTP_HOST")).strip()
        port_raw = port if port is not None else _env("WB_SMTP_PORT") or "587"
        self.port = int(port_raw or 587)
        self.user = (user if user is not None else _env("WB_SMTP_USER")).strip()
        self.password = (password if password is not None else _env("WB_SMTP_PASSWORD")).strip()
        self.from_addr = (from_addr if from_addr is not None else _env("WB_SMTP_FROM") or self.user).strip()
        tls_env = _env("WB_SMTP_TLS") or "1"
        self.use_tls = use_tls if use_tls is not None else tls_env in {"1", "true", "yes", "on"}

    def configured(self) -> bool:
        return bool(self.host and self.from_addr)

    def send_text(
        self,
        to_addr: str,
        subject: str,
        text: str,
        *,
        require_outbound_flag: bool = True,
    ) -> ConnectorResult:
        if require_outbound_flag and not outbound_allowed():
            return ConnectorResult(
                ok=False,
                provider="email",
                action="send",
                data={"to": to_addr, "queued": False},
                error="WB_ALLOW_OUTBOUND not set — email not sent",
            )
        if not self.configured():
            raise ConnectorError("SMTP not configured (WB_SMTP_HOST / WB_SMTP_FROM)")
        msg = EmailMessage()
        msg["From"] = self.from_addr
        msg["To"] = to_addr
        msg["Subject"] = subject
        msg.set_content(text)
        try:
            if self.use_tls:
                context = ssl.create_default_context()
                with smtplib.SMTP(self.host, self.port, timeout=20) as smtp:
                    smtp.starttls(context=context)
                    if self.user:
                        smtp.login(self.user, self.password)
                    smtp.send_message(msg)
            else:
                with smtplib.SMTP(self.host, self.port, timeout=20) as smtp:
                    if self.user:
                        smtp.login(self.user, self.password)
                    smtp.send_message(msg)
            return ConnectorResult(
                ok=True,
                provider="email",
                action="send",
                data={"to": to_addr, "subject": subject},
            )
        except (OSError, smtplib.SMTPException) as exc:
            return ConnectorResult(
                ok=False,
                provider="email",
                action="send",
                data={"to": to_addr},
                error=str(exc)[:300],
            )


class WebhookConnector:
    """POST JSON ``{"text": ...}`` to an arbitrary HTTPS URL."""

    def __init__(self, url: str | None = None) -> None:
        self.url = (url if url is not None else _env("WB_WEBHOOK_URL")).strip()

    def configured(self) -> bool:
        return bool(self.url)

    def send_text(
        self,
        text: str,
        *,
        url: str | None = None,
        require_outbound_flag: bool = True,
        extra: dict[str, Any] | None = None,
    ) -> ConnectorResult:
        target = (url or self.url).strip()
        if require_outbound_flag and not outbound_allowed():
            return ConnectorResult(
                ok=False,
                provider="webhook",
                action="post",
                data={"url": target, "queued": False},
                error="WB_ALLOW_OUTBOUND not set — webhook not sent",
            )
        if not target:
            raise ConnectorError("webhook URL empty")
        parsed = urlparse(target)
        if parsed.scheme not in {"http", "https"}:
            raise ConnectorError(f"unsupported webhook scheme: {parsed.scheme}")
        body = {"text": text}
        if extra:
            body.update(extra)
        data = json.dumps(body).encode("utf-8")
        req = urllib.request.Request(
            target,
            data=data,
            method="POST",
            headers={"Content-Type": "application/json", "User-Agent": "xiongbao-webhook/1"},
        )
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                return ConnectorResult(
                    ok=True,
                    provider="webhook",
                    action="post",
                    data={"url": target, "status": getattr(resp, "status", 200)},
                )
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            return ConnectorResult(
                ok=False,
                provider="webhook",
                action="post",
                data={"url": target},
                error=str(exc)[:300],
            )


def resolve_message_messaging(
    target: str,
    text: str,
    *,
    require_outbound_flag: bool = True,
) -> ConnectorResult | None:
    t = target.strip()
    lower = t.lower()
    if lower.startswith("email:") or lower.startswith("mailto:"):
        addr = t.split(":", 1)[1].strip()
        subject = _env("WB_EMAIL_SUBJECT") or "WorkBuddy notification"
        return EmailConnector().send_text(
            addr, subject, text, require_outbound_flag=require_outbound_flag
        )
    if lower.startswith("webhook:"):
        url = t.split(":", 1)[1].strip()
        if url.startswith("//"):
            url = "https:" + url
        return WebhookConnector(url).send_text(text, require_outbound_flag=require_outbound_flag)
    if lower == "webhook" or lower == "webhook:default":
        return WebhookConnector().send_text(text, require_outbound_flag=require_outbound_flag)
    return None


def probe_messaging_status() -> dict[str, Any]:
    email = EmailConnector()
    hook = WebhookConnector()
    return {
        "email": {"configured": email.configured(), "host_set": bool(email.host)},
        "webhook": {"configured": hook.configured(), "url_set": bool(hook.url)},
    }
