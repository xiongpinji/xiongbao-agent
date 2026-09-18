# SPDX-License-Identifier: MIT
"""Bridge Chrome CDP page events into TeachRecorder.

Injects a page script that queues click / input / navigation signals into
``window.__wbTeachQueue``. The bridge polls and appends to TeachRecorder.
"""

from __future__ import annotations

import time
from typing import Any

from .cdp_client import CdpClient, CdpError, list_targets
from .recorder import TeachRecorder

INJECT_JS = r"""
(() => {
  if (window.__wbTeachInstalled) return "already";
  window.__wbTeachInstalled = true;
  window.__wbTeachQueue = window.__wbTeachQueue || [];
  const push = (ev) => { try { window.__wbTeachQueue.push(ev); } catch (e) {} };
  const cssPath = (el) => {
    if (!el || !el.tagName) return "";
    if (el.id) return "#" + el.id;
    const parts = [];
    let cur = el;
    for (let i = 0; cur && cur.nodeType === 1 && i < 5; i++) {
      let part = cur.tagName.toLowerCase();
      if (cur.classList && cur.classList.length)
        part += "." + Array.from(cur.classList).slice(0, 2).join(".");
      parts.unshift(part);
      cur = cur.parentElement;
    }
    return parts.join(" > ");
  };
  document.addEventListener("click", (e) => {
    const t = e.target;
    push({ kind: "click", selector: cssPath(t), text: (t && t.innerText || "").slice(0, 80), href: t && t.href || "" });
  }, true);
  document.addEventListener("change", (e) => {
    const t = e.target;
    if (!t) return;
    const val = (t.value != null ? String(t.value) : "").slice(0, 200);
    push({ kind: "type", selector: cssPath(t), value: val });
  }, true);
  push({ kind: "navigate", url: location.href, summary: "page ready" });
  return "ok";
})()
"""

DRAIN_JS = r"""
(() => {
  const q = window.__wbTeachQueue || [];
  window.__wbTeachQueue = [];
  return q;
})()
"""


class CdpTeachSession:
    """Attach to a Chrome page and record user actions into TeachRecorder."""

    def __init__(
        self,
        recorder: TeachRecorder,
        client: CdpClient,
        *,
        poll_interval: float = 0.4,
    ) -> None:
        self.recorder = recorder
        self.client = client
        self.poll_interval = poll_interval
        self._seen_nav: set[str] = set()

    @classmethod
    def attach(
        cls,
        recorder: TeachRecorder,
        *,
        host: str = "127.0.0.1",
        port: int = 9222,
        navigate_url: str | None = None,
        page_url_substr: str | None = None,
    ) -> CdpTeachSession:
        client = CdpClient.connect(host=host, port=port, page_url_substr=page_url_substr)
        session = cls(recorder, client)
        client.call("Page.enable")
        client.call("Runtime.enable")
        if navigate_url:
            client.call("Page.navigate", {"url": navigate_url})
            time.sleep(0.8)
            recorder.navigate(navigate_url, f"CDP 打开 {navigate_url}")
            session._seen_nav.add(navigate_url)
        session._install_hooks()
        return session

    def _install_hooks(self) -> None:
        self.client.call("Runtime.evaluate", {"expression": INJECT_JS, "returnByValue": True})

    def _apply_event(self, ev: dict[str, Any]) -> None:
        kind = str(ev.get("kind") or "")
        if kind == "navigate":
            url = str(ev.get("url") or "")
            if url and url not in self._seen_nav:
                self._seen_nav.add(url)
                self.recorder.navigate(url, str(ev.get("summary") or f"导航到 {url}"))
        elif kind == "click":
            sel = str(ev.get("selector") or ev.get("href") or "unknown")
            summary = str(ev.get("text") or "").strip() or f"点击 {sel}"
            self.recorder.click(sel, summary[:120])
        elif kind == "type":
            sel = str(ev.get("selector") or "input")
            val = str(ev.get("value") or "")
            self.recorder.type_text(sel, val, f"输入到 {sel}")

    def poll_once(self) -> int:
        result = self.client.call(
            "Runtime.evaluate",
            {"expression": DRAIN_JS, "returnByValue": True},
        )
        value = (result or {}).get("result", {}).get("value")
        if not isinstance(value, list):
            return 0
        n = 0
        for item in value:
            if isinstance(item, dict):
                self._apply_event(item)
                n += 1
        return n

    def record_for(self, seconds: float) -> int:
        """Poll for *seconds*; return number of drained events."""
        deadline = time.time() + max(0.0, seconds)
        total = 0
        while time.time() < deadline:
            total += self.poll_once()
            time.sleep(self.poll_interval)
        return total

    def close(self) -> None:
        self.client.close()


def cdp_available(host: str = "127.0.0.1", port: int = 9222) -> bool:
    try:
        list_targets(host, port, timeout=1.5)
        return True
    except CdpError:
        return False


def open_blank_and_record(
    recorder: TeachRecorder,
    *,
    url: str,
    duration_sec: float = 5.0,
    host: str = "127.0.0.1",
    port: int = 9222,
) -> int:
    """Convenience: navigate + poll. Raises CdpError if Chrome not listening."""
    session = CdpTeachSession.attach(
        recorder, host=host, port=port, navigate_url=url, page_url_substr=None
    )
    try:
        return session.record_for(duration_sec)
    finally:
        session.close()
