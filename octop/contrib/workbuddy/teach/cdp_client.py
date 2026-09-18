# SPDX-License-Identifier: MIT
"""Chrome DevTools Protocol client (stdlib WebSocket)."""

from __future__ import annotations

import json
import socket
import urllib.error
import urllib.request
from typing import Any, Protocol

from .ws_client import SimpleWebSocket, WebSocketError


class Transport(Protocol):
    def send_text(self, text: str) -> None: ...

    def recv_text(self, *, timeout: float | None = None) -> str: ...

    def close(self) -> None: ...


class CdpError(RuntimeError):
    pass


def list_targets(host: str = "127.0.0.1", port: int = 9222, *, timeout: float = 3.0) -> list[dict[str, Any]]:
    url = f"http://{host}:{port}/json/list"
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.URLError as exc:
        raise CdpError(
            f"Chrome CDP not reachable at {url}. "
            "Start Chrome with --remote-debugging-port=9222"
        ) from exc
    if not isinstance(data, list):
        raise CdpError("unexpected /json/list payload")
    return [t for t in data if isinstance(t, dict)]


def pick_page_ws_url(targets: list[dict[str, Any]], *, prefer_url: str | None = None) -> str:
    pages = [t for t in targets if t.get("type") == "page" and t.get("webSocketDebuggerUrl")]
    if not pages:
        raise CdpError("no page targets with webSocketDebuggerUrl")
    if prefer_url:
        for t in pages:
            if prefer_url in str(t.get("url") or ""):
                return str(t["webSocketDebuggerUrl"])
    return str(pages[0]["webSocketDebuggerUrl"])


class CdpClient:
    """JSON-RPC over CDP WebSocket."""

    def __init__(self, transport: Transport) -> None:
        self._ws = transport
        self._next_id = 1

    @classmethod
    def connect(
        cls,
        *,
        host: str = "127.0.0.1",
        port: int = 9222,
        page_url_substr: str | None = None,
        timeout: float = 10.0,
    ) -> CdpClient:
        targets = list_targets(host, port, timeout=timeout)
        ws_url = pick_page_ws_url(targets, prefer_url=page_url_substr)
        transport = SimpleWebSocket.connect(ws_url, timeout=timeout)
        return cls(transport)

    def call(self, method: str, params: dict[str, Any] | None = None, *, timeout: float = 15.0) -> Any:
        msg_id = self._next_id
        self._next_id += 1
        payload = {"id": msg_id, "method": method, "params": params or {}}
        self._ws.send_text(json.dumps(payload))
        attempts = max(1, int(timeout / 0.25))
        for _ in range(attempts):
            try:
                raw = self._ws.recv_text(timeout=0.25)
            except (TimeoutError, socket.timeout, OSError):
                continue
            except WebSocketError:
                raise
            data = json.loads(raw)
            if data.get("id") == msg_id:
                if "error" in data:
                    raise CdpError(f"{method}: {data['error']}")
                return data.get("result")
        raise CdpError(f"timeout waiting for {method}")

    def close(self) -> None:
        self._ws.close()
