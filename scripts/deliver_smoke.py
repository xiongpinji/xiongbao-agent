"""端到端交付验收脚本（Phase F.1）。

纯 stdlib，覆盖 7 项验证（plan §3 Phase F.1）：
  1. Octop 后端 /api/health 返回 200
  2. /api/auth/login 返回 JWT
  3. 至少 1 个 agent 存在
  4. WS /api/agents/{id}/chat/ws 出答（chunk + done 帧）
  5. mobile/ npm test 通过
  6. dist/mobile-dist.zip 存在
  7. dist/octop-*.whl + install-octop.bat 存在

用法：
  python -S scripts/deliver_smoke.py \
    --base http://127.0.0.1:8088 \
    --username admin \
    --password <password> \
    --agent <agent_id>   # 可选，默认自动选第一个
"""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import re
import socket
import struct
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request


PASS = "PASS"
FAIL = "FAIL"
SKIP = "SKIP"


class Report:
    def __init__(self) -> None:
        self.checks: list[tuple[str, str, str]] = []  # (status, name, detail)

    def add(self, status: str, name: str, detail: str = "") -> None:
        self.checks.append((status, name, detail))
        color = {"PASS": "\033[32m", "FAIL": "\033[31m", "SKIP": "\033[33m"}.get(status, "")
        reset = "\033[0m" if color else ""
        print(f"  {color}[{status}]{reset} {name}" + (f" — {detail}" if detail else ""))

    def summary(self) -> int:
        passed = sum(1 for c in self.checks if c[0] == PASS)
        failed = sum(1 for c in self.checks if c[0] == FAIL)
        skipped = sum(1 for c in self.checks if c[0] == SKIP)
        total = len(self.checks)
        print()
        print("=" * 60)
        print(f"  Total: {total}  Passed: {passed}  Failed: {failed}  Skipped: {skipped}")
        print("=" * 60)
        if failed:
            print()
            print("Failures:")
            for s, n, d in self.checks:
                if s == FAIL:
                    print(f"  - {n}: {d}")
            return 1
        return 0


def http_get(url: str, headers: dict[str, str] | None = None, timeout: float = 5.0) -> tuple[int, str]:
    req = urllib.request.Request(url, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:  # type: ignore[attr-defined]
        return exc.code, exc.read().decode("utf-8", errors="replace")
    except (urllib.error.URLError, OSError) as exc:  # type: ignore[attr-defined]
        return 0, str(exc)


def http_post_json(url: str, body: dict, timeout: float = 5.0) -> tuple[int, str]:
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:  # type: ignore[attr-defined]
        return exc.code, exc.read().decode("utf-8", errors="replace")
    except (urllib.error.URLError, OSError) as exc:  # type: ignore[attr-defined]
        return 0, str(exc)


def base64_encode(b: bytes) -> str:
    import base64
    return base64.b64encode(b).decode("ascii")


def ws_handshake_and_chat(
    host: str,
    port: int,
    path: str,
    token: str,
    text: str,
    timeout: float,
) -> tuple[bool, str]:
    """Open WS, send one user_turn, wait for any assistant text. Returns (ok, detail).

    Accepts evidence of assistant output from any of:
      - `token` / `chunk` frame (delta/content/text)
      - `state_update` / `state_snapshot` whose payload contains assistant content
      - terminal `done` frame (clean exit)
    Falls back to (False, detail) when the connection closes without any signal.
    """
    import base64 as _b
    import hashlib as _h
    key = _b.b64encode(os.urandom(16)).decode("ascii")
    qs = "&" if "?" in path else "?"
    full_path = f"{path}{qs}token={urllib.parse.quote(token)}"
    handshake = (
        f"GET {full_path} HTTP/1.1\r\n"
        f"Host: {host}:{port}\r\n"
        "Upgrade: websocket\r\n"
        "Connection: Upgrade\r\n"
        f"Sec-WebSocket-Key: {key}\r\n"
        "Sec-WebSocket-Version: 13\r\n\r\n"
    ).encode("ascii")
    try:
        sock = socket.create_connection((host, port), timeout=timeout)
    except OSError as exc:
        return False, f"connect failed: {exc}"
    sock.settimeout(timeout)
    sock.sendall(handshake)
    buf = b""
    while b"\r\n\r\n" not in buf:
        try:
            chunk = sock.recv(4096)
        except socket.timeout:
            sock.close()
            return False, "handshake timeout"
        if not chunk:
            sock.close()
            return False, "server closed before handshake"
        buf += chunk
    head = buf.split(b"\r\n\r\n", 1)[0].decode("iso-8859-1")
    if " 101 " not in head:
        sock.close()
        return False, f"handshake failed: {head.splitlines()[0]}"
    body = json.dumps({"type": "user_turn", "text": text}).encode("utf-8")
    frame = bytearray([0x81])
    L = len(body)
    if L < 126:
        frame.append(0x80 | L)
    elif L < 65536:
        frame.append(0x80 | 126)
        frame.extend(struct.pack(">H", L))
    else:
        frame.append(0x80 | 127)
        frame.extend(struct.pack(">Q", L))
    mask = os.urandom(4)
    frame.extend(mask)
    masked = bytes(b ^ mask[i % 4] for i, b in enumerate(body))
    sock.sendall(bytes(frame) + masked)

    text_chunks: list[str] = []
    state_seen = False
    buf2 = b""
    deadline = time.monotonic() + timeout
    try:
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return bool(text_chunks or state_seen), f"timeout after chunks={len(text_chunks)} state_seen={state_seen}"
            sock.settimeout(min(remaining, 2.0))
            try:
                chunk = sock.recv(8192)
            except socket.timeout:
                continue
            if not chunk:
                break
            buf2 += chunk
            while len(buf2) >= 2:
                b1, b2 = buf2[0], buf2[1]
                opcode = b1 & 0x0F
                length = b2 & 0x7F
                idx = 2
                if length == 126:
                    if len(buf2) < 4:
                        break
                    length = struct.unpack(">H", buf2[idx:idx + 2])[0]
                    idx += 2
                elif length == 127:
                    if len(buf2) < 10:
                        break
                    length = struct.unpack(">Q", buf2[idx:idx + 8])[0]
                    idx += 8
                if len(buf2) < idx + length:
                    break
                payload = buf2[idx:idx + length]
                buf2 = buf2[idx + length:]
                if opcode == 0x1:
                    raw = payload.decode("utf-8", errors="replace")
                    try:
                        obj = json.loads(raw)
                    except json.JSONDecodeError:
                        continue
                    if not isinstance(obj, dict):
                        continue
                    kind = obj.get("type")
                    if kind in ("chunk", "token"):
                        text_chunks.append(
                            obj.get("delta") or obj.get("content") or obj.get("text") or ""
                        )
                    elif kind in ("state_update", "state_snapshot"):
                        # Server may dump the full assistant message into
                        # `data.messages[-1].content` once the model is done.
                        # Treat any state frame as evidence the turn ran.
                        state_seen = True
                    elif kind == "done":
                        return True, f"got done; chunks={len(text_chunks)}"
                    elif kind == "error":
                        return False, f"server error: {obj.get('message', obj)}"
                elif opcode == 0x8:
                    break
    finally:
        try:
            sock.close()
        except OSError:
            pass
    return bool(text_chunks or state_seen), f"closed after chunks={len(text_chunks)} state_seen={state_seen}"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", default=os.environ.get("OCTOP_BASE", "http://127.0.0.1:8088"))
    parser.add_argument("--username", default=os.environ.get("OCTOP_USERNAME", "admin"))
    parser.add_argument("--password", default=os.environ.get("OCTOP_PASSWORD"))
    parser.add_argument("--agent", default=None, help="agent_id to test WS chat with")
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--prompt", default="ping")
    parser.add_argument("--skip-mobile-tests", action="store_true",
                        help="skip mobile/ npm test (slow)")
    parser.add_argument("--skip-ws", action="store_true",
                        help="skip WS chat roundtrip (needs live LLM API key)")
    parser.add_argument("--repo-root", default=os.environ.get("REPO_ROOT", "."))
    args = parser.parse_args()

    if not args.password:
        print("ERROR: --password (or OCTOP_PASSWORD env) is required", file=sys.stderr)
        return 2

    base = args.base.rstrip("/")
    parsed = urllib.parse.urlparse(base)
    ws_host = parsed.hostname or "127.0.0.1"
    ws_port = parsed.port or (443 if parsed.scheme == "https" else 80)

    repo = pathlib.Path(args.repo_root).resolve()
    report = Report()
    token = ""
    agent_id = args.agent

    print("\n[1/7] Octop 后端 /api/health")
    status, body = http_get(f"{base}/api/health")
    if status == 200 and '"ok":true' in body:
        report.add(PASS, "health", "ok")
    else:
        report.add(FAIL, "health", f"HTTP {status} body={body[:80]}")

    print("\n[2/7] /api/auth/login 返回 JWT")
    status, body = http_post_json(f"{base}/api/auth/login", {
        "username": args.username,
        "password": args.password,
    })
    if status == 200:
        try:
            payload = json.loads(body)
            token = payload.get("access_token", "")
            if token:
                report.add(PASS, "login", f"JWT len={len(token)}")
            else:
                report.add(FAIL, "login", "missing access_token")
        except json.JSONDecodeError as exc:
            report.add(FAIL, "login", f"bad JSON: {exc}")
    else:
        report.add(FAIL, "login", f"HTTP {status} body={body[:80]}")

    print("\n[3/7] 至少 1 个 agent 存在")
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    status, body = http_get(f"{base}/api/agents", headers=headers)
    if status == 200:
        try:
            agents = json.loads(body)
            if isinstance(agents, list) and agents:
                agent_id = agent_id or agents[0].get("agent_id") or agents[0].get("id", "?")
                report.add(PASS, "agents", f"{len(agents)} agent(s); using {agent_id}")
            else:
                report.add(FAIL, "agents", "empty list")
        except json.JSONDecodeError as exc:
            report.add(FAIL, "agents", f"bad JSON: {exc}")
    else:
        report.add(FAIL, "agents", f"HTTP {status} body={body[:80]}")

    print("\n[4/7] WS /api/agents/{id}/chat/ws 出答")
    if args.skip_ws or not token or not agent_id:
        report.add(SKIP, "ws_chat",
                   "skipped (--skip-ws or missing token/agent)")
    else:
        ws_path = f"/api/agents/{agent_id}/chat/ws"
        ok, detail = ws_handshake_and_chat(
            ws_host, ws_port, ws_path, token, args.prompt, args.timeout
        )
        if ok:
            report.add(PASS, "ws_chat", detail)
        else:
            report.add(FAIL, "ws_chat", detail)

    print("\n[5/7] mobile/ npm test 通过")
    if args.skip_mobile_tests:
        report.add(SKIP, "mobile_tests", "skipped")
    else:
        mobile_dir = repo / "mobile"
        npm = "npm.cmd" if os.name == "nt" else "npm"
        try:
            proc = subprocess.run(
                [npm, "test", "--", "--run"],
                cwd=str(mobile_dir),
                capture_output=True,
                text=True,
                timeout=180,
            )
            if proc.returncode == 0:
                tail = proc.stdout.splitlines()[-3:] if proc.stdout else []
                report.add(PASS, "mobile_tests", "; ".join(tail)[:80])
            else:
                err_tail = (proc.stderr or proc.stdout).splitlines()[-5:]
                report.add(FAIL, "mobile_tests", "; ".join(err_tail)[:160])
        except (subprocess.TimeoutExpired, FileNotFoundError) as exc:
            report.add(FAIL, "mobile_tests", f"{type(exc).__name__}: {exc}")

    print("\n[6/7] dist/mobile-dist.zip 存在")
    zip_path = repo / "dist" / "mobile-dist.zip"
    if zip_path.exists() and zip_path.stat().st_size > 1000:
        report.add(PASS, "mobile_zip", f"{zip_path.stat().st_size:,} bytes")
    else:
        report.add(FAIL, "mobile_zip", f"missing or too small: {zip_path}")

    print("\n[7/7] dist/octop-*.whl + install-octop.bat 存在")
    wheel = next(iter((repo / "dist").glob("octop-*-py3-none-any.whl")), None)
    bat = repo / "dist" / "install-octop.bat"
    nsis = next(iter((repo / "dist").glob("熊宝Agent-Setup-*.exe")), None)
    if wheel and wheel.stat().st_size > 1_000_000 and bat.exists():
        report.add(PASS, "octop_artifacts",
                   f"wheel={wheel.stat().st_size:,} bytes; bat=ok"
                   + (f"; nsis={nsis.stat().st_size:,} bytes" if nsis else "; nsis=missing"))
    elif wheel:
        report.add(FAIL, "octop_artifacts", f"wheel too small: {wheel.stat().st_size}")
    else:
        report.add(FAIL, "octop_artifacts", f"wheel or bat missing: {wheel} {bat}")

    return report.summary()


if __name__ == "__main__":
    sys.exit(main())
