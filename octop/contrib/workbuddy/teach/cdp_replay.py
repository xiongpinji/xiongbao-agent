# SPDX-License-Identifier: MIT
"""CDP UI replay — click / type via Runtime.evaluate (stdlib)."""

from __future__ import annotations

import json
from typing import Any

from .cdp_client import CdpClient, CdpError


def _js_string(s: str) -> str:
    return json.dumps(s, ensure_ascii=False)


class CdpReplaySession:
    """Replay recorded UI actions against an attached Chrome page."""

    def __init__(self, client: CdpClient) -> None:
        self.client = client

    @classmethod
    def attach(
        cls,
        *,
        host: str = "127.0.0.1",
        port: int = 9222,
        page_url_substr: str | None = None,
    ) -> CdpReplaySession:
        client = CdpClient.connect(host=host, port=port, page_url_substr=page_url_substr)
        client.call("Runtime.enable")
        client.call("Page.enable")
        return cls(client)

    def _eval(self, expression: str) -> Any:
        result = self.client.call(
            "Runtime.evaluate",
            {
                "expression": expression,
                "returnByValue": True,
                "awaitPromise": True,
            },
        )
        remote = (result or {}).get("result") or {}
        if remote.get("subtype") == "error" or (result or {}).get("exceptionDetails"):
            raise CdpError(f"evaluate failed: {(result or {}).get('exceptionDetails') or remote}")
        return remote.get("value")

    def click(self, selector: str) -> dict[str, Any]:
        sel = _js_string(selector)
        expr = f"""
(() => {{
  const el = document.querySelector({sel});
  if (!el) return {{ ok: false, error: "not found", selector: {sel} }};
  el.scrollIntoView({{ block: "center", inline: "center" }});
  el.dispatchEvent(new MouseEvent("click", {{ bubbles: true, cancelable: true, view: window }}));
  if (typeof el.click === "function") el.click();
  return {{ ok: true, selector: {sel}, tag: el.tagName }};
}})()
"""
        value = self._eval(expr)
        if not isinstance(value, dict):
            return {"ok": False, "error": "unexpected evaluate result", "raw": value}
        return value

    def type_text(self, selector: str, text: str) -> dict[str, Any]:
        sel = _js_string(selector)
        val = _js_string(text)
        expr = f"""
(() => {{
  const el = document.querySelector({sel});
  if (!el) return {{ ok: false, error: "not found", selector: {sel} }};
  el.focus();
  const proto = el.tagName === "TEXTAREA" || el.tagName === "INPUT"
    ? window.HTMLInputElement.prototype
    : el;
  const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, "value")
    || Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, "value");
  if (setter && setter.set) setter.set.call(el, {val});
  else el.value = {val};
  el.dispatchEvent(new Event("input", {{ bubbles: true }}));
  el.dispatchEvent(new Event("change", {{ bubbles: true }}));
  return {{ ok: true, selector: {sel}, chars: String({val}).length }};
}})()
"""
        value = self._eval(expr)
        if not isinstance(value, dict):
            return {"ok": False, "error": "unexpected evaluate result", "raw": value}
        return value

    def navigate(self, url: str) -> dict[str, Any]:
        self.client.call("Page.navigate", {"url": url})
        return {"ok": True, "url": url}

    def close(self) -> None:
        self.client.close()
