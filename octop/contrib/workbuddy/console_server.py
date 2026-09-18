# SPDX-License-Identifier: MIT
"""WorkBuddy Console — stdlib HTTP status UI (no Octop Dashboard fork)."""

from __future__ import annotations

import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from .hub import hub_status

_STATIC = Path(__file__).resolve().parent / "console" / "index.html"


class _Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt: str, *args: object) -> None:  # noqa: A003
        return

    def _send(self, code: int, body: bytes, content_type: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path in {"/api/status", "/api/hub"}:
            payload = json.dumps(hub_status(), ensure_ascii=False, indent=2).encode("utf-8")
            self._send(200, payload, "application/json; charset=utf-8")
            return
        if path in {"/", "/index.html"}:
            if not _STATIC.is_file():
                self._send(404, b"console missing", "text/plain; charset=utf-8")
                return
            self._send(200, _STATIC.read_bytes(), "text/html; charset=utf-8")
            return
        self._send(404, b"not found", "text/plain; charset=utf-8")


def serve(*, host: str = "127.0.0.1", port: int = 8010) -> None:
    httpd = ThreadingHTTPServer((host, port), _Handler)
    print(f"[wb-console] http://{host}:{port}/  (GET /api/status)")
    httpd.serve_forever()


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="console_server")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8010)
    args = p.parse_args(argv)
    serve(host=args.host, port=args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
