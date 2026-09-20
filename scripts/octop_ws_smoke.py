"""Octop 后端 LLM 出答验收脚本（Phase A.3）。

纯 stdlib 实现 WebSocket 客户端（RFC 6455），无需安装第三方依赖。
用法：

    python scripts/octop_ws_smoke.py \
        --base http://127.0.0.1:8088 \
        --username admin \
        --password <你的密码> \
        --agent <agent_id> \
        --prompt "用一句话介绍自己" \
        --timeout 30

脚本会自动：
  1. POST /api/auth/login 拿 JWT
  2. 打开 ws://<base>/api/agents/<id>/chat/ws?token=<jwt>
  3. 发 user_turn JSON
  4. 把 chunk 流拼起来，遇到 done / error / close 退出
  5. 把合并后的回答打印到 stdout

退出码：
  0 = 收到 done 帧且 chunk 拼接成功
  1 = 网络/认证/参数错误
  2 = 收到 error 帧或 done 帧前连接断开
  3 = 超时
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import socket
import struct
import sys
import urllib.parse
import urllib.request
from typing import Any


def http_post_json(url: str, payload: dict[str, Any], timeout: float) -> tuple[int, Any]:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read()
            try:
                return resp.status, json.loads(body)
            except json.JSONDecodeError:
                return resp.status, body.decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:  # type: ignore[attr-defined]
        body = exc.read()
        try:
            return exc.code, json.loads(body)
        except json.JSONDecodeError:
            return exc.code, body.decode("utf-8", errors="replace")
    except (urllib.error.URLError, OSError) as exc:  # type: ignore[attr-defined]
        return 0, f"network error: {exc}"


def parse_ws_frame(payload: bytes) -> tuple[int, bytes]:
    """解析单个 WS 帧（仅服务端 → 客户端文本/二进制/关闭）。"""
    if len(payload) < 2:
        raise ValueError("frame too short")
    b1, b2 = payload[0], payload[1]
    opcode = b1 & 0x0F
    masked = (b2 & 0x80) != 0
    length = b2 & 0x7F
    idx = 2
    if length == 126:
        if len(payload) < idx + 2:
            raise ValueError("frame too short for 16-bit length")
        length = struct.unpack(">H", payload[idx:idx + 2])[0]
        idx += 2
    elif length == 127:
        if len(payload) < idx + 8:
            raise ValueError("frame too short for 64-bit length")
        length = struct.unpack(">Q", payload[idx:idx + 8])[0]
        idx += 8
    if masked:
        if len(payload) < idx + 4:
            raise ValueError("frame too short for mask")
        mask = payload[idx:idx + 4]
        idx += 4
    else:
        mask = None
    end = idx + length
    if len(payload) < end:
        raise ValueError("incomplete frame")
    body = payload[idx:end]
    if mask:
        body = bytes(b ^ mask[i % 4] for i, b in enumerate(body))
    return opcode, body


def build_ws_handshake(host: str, port: int, path: str, token: str) -> dict[str, str]:
    key = base64.b64encode(os.urandom(16)).decode("ascii")
    headers = {
        "Host": f"{host}:{port}",
        "Upgrade": "websocket",
        "Connection": "Upgrade",
        "Sec-WebSocket-Key": key,
        "Sec-WebSocket-Version": "13",
    }
    if token:
        sep = "&" if "?" in path else "?"
        full_path = f"{path}{sep}token={urllib.parse.quote(token)}"
    else:
        full_path = path
    request_lines = [f"GET {full_path} HTTP/1.1"]
    for k, v in headers.items():
        request_lines.append(f"{k}: {v}")
    request_lines.append("")
    request_lines.append("")
    return {"request": "\r\n".join(request_lines), "key": key}


def ws_exchange(
    host: str,
    port: int,
    path: str,
    token: str,
    outbound_payloads: list[bytes],
    read_timeout: float,
    max_total: float,
    verbose: bool = False,
) -> tuple[str, list[Any]]:
    """打开 WS，发送若干 user_turn，等待 done 或 close。返回 (status, frames)。"""
    sock = socket.create_connection((host, port), timeout=read_timeout)
    sock.settimeout(read_timeout)
    hs = build_ws_handshake(host, port, path, token)
    sock.sendall(hs["request"].encode("ascii"))
    buf = b""
    while b"\r\n\r\n" not in buf:
        chunk = sock.recv(4096)
        if not chunk:
            raise ConnectionError("server closed before handshake complete")
        buf += chunk
    head, _, rest = buf.partition(b"\r\n\r\n")
    head_str = head.decode("iso-8859-1")
    status_line = head_str.splitlines()[0]
    if " 101 " not in status_line:
        raise ConnectionError(f"handshake failed: {status_line}")
    expected_accept = base64.b64encode(
        hashlib.sha1((hs["key"] + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode("ascii")).digest()
    ).decode("ascii")
    if "Sec-WebSocket-Accept:" in head_str and expected_accept not in head_str:
        raise ConnectionError("Sec-WebSocket-Accept mismatch")
    if verbose:
        sys.stderr.write(f"[ws] handshake ok, sending {len(outbound_payloads)} frame(s)\n")
    buf = rest
    for payload in outbound_payloads:
        frame = build_ws_text_frame(payload)
        sock.sendall(frame)
    frames: list[Any] = []
    text_chunks: list[str] = []
    sock.settimeout(read_timeout)
    import time
    start = time.monotonic()
    try:
        while True:
            if time.monotonic() - start > max_total:
                return ("timeout", frames + [{"text": "".join(text_chunks), "chunks": list(text_chunks)}])
            try:
                chunk = sock.recv(8192)
            except socket.timeout:
                continue
            if not chunk:
                if verbose:
                    sys.stderr.write(f"[ws] closed after {len(frames)} frames\n")
                return ("closed", frames)
            buf += chunk
            while True:
                if len(buf) < 2:
                    break
                b1, b2 = buf[0], buf[1]
                length = b2 & 0x7F
                idx = 2
                if length == 126:
                    if len(buf) < idx + 2:
                        break
                    length = struct.unpack(">H", buf[idx:idx + 2])[0]
                    idx += 2
                elif length == 127:
                    if len(buf) < idx + 8:
                        break
                    length = struct.unpack(">Q", buf[idx:idx + 8])[0]
                    idx += 8
                masked = (b2 & 0x80) != 0
                if masked:
                    if len(buf) < idx + 4:
                        break
                    idx += 4
                if len(buf) < idx + length:
                    break
                payload_bytes = bytes(buf[idx:idx + length])
                buf = buf[idx + length:]
                opcode = b1 & 0x0F
                if opcode == 0x1:  # text
                    try:
                        decoded = payload_bytes.decode("utf-8", errors="replace")
                    except Exception:
                        decoded = payload_bytes.decode("utf-8", errors="replace")
                    text_chunks.append(decoded)
                    frames.append(decoded)
                    try:
                        obj = json.loads(decoded)
                    except json.JSONDecodeError:
                        obj = None
                    if isinstance(obj, dict):
                        kind = obj.get("type")
                        if kind == "token":
                            # harness streams `token.content`, dashboard
                            # sometimes uses `chunk.delta`. Cover both.
                            text += obj.get("content") or obj.get("delta") or obj.get("text") or ""
                        elif kind == "chunk":
                            text += obj.get("delta") or obj.get("content") or obj.get("text") or ""
                        if kind == "done":
                            return ("done", frames + [{"text": text, "chunks": list(text_chunks)}])
                        if kind == "error":
                            return ("error", frames + [obj])
                elif opcode == 0x8:  # close
                    return ("closed", frames)
                elif opcode == 0x9:  # ping
                    sock.sendall(b"\x8a\x00")
                elif opcode == 0xA:  # pong
                    pass
                # binary / continuation ignored for now
    finally:
        try:
            sock.close()
        except OSError:
            pass


def build_ws_text_frame(payload: bytes) -> bytes:
    header = bytearray()
    header.append(0x81)  # FIN + text
    length = len(payload)
    mask_bit = 0x00
    if length < 126:
        header.append(mask_bit | length)
    elif length < (1 << 16):
        header.append(mask_bit | 126)
        header.extend(struct.pack(">H", length))
    else:
        header.append(mask_bit | 127)
        header.extend(struct.pack(">Q", length))
    return bytes(header) + payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", default="http://127.0.0.1:8088")
    parser.add_argument("--username", default="admin")
    parser.add_argument("--password", required=True)
    parser.add_argument("--agent", required=True, help="agent_id for chat/ws")
    parser.add_argument("--prompt", default="用一句话介绍自己")
    parser.add_argument("--timeout", type=float, default=30.0, help="per-read timeout in seconds")
    parser.add_argument("--max-total", type=float, default=45.0, help="overall wall-clock budget")
    args = parser.parse_args()

    base = args.base.rstrip("/")
    parsed = urllib.parse.urlparse(base)
    host = parsed.hostname or "127.0.0.1"
    port = parsed.port or (443 if parsed.scheme == "https" else 80)

    login_url = f"{base}/api/auth/login"
    print(f"[1/3] POST {login_url}", file=sys.stderr)
    status, body = http_post_json(login_url, {"username": args.username, "password": args.password}, args.timeout)
    if status != 200 or not isinstance(body, dict):
        print(f"login failed: HTTP {status} body={body!r}", file=sys.stderr)
        return 1
    token = body.get("access_token") or body.get("token") or ""
    if not token:
        print(f"login response missing access_token: {body!r}", file=sys.stderr)
        return 1
    user = body.get("user", {})
    print(f"  ok: user={user.get('username', '?')} role={user.get('role', '?')}", file=sys.stderr)

    ws_scheme = "wss" if parsed.scheme == "https" else "ws"
    ws_path = f"/api/agents/{args.agent}/chat/ws"
    print(f"[2/3] WS {ws_scheme}://{host}:{port}{ws_path}?token=***", file=sys.stderr)

    outbound = json.dumps({
        "type": "user_turn",
        "text": args.prompt,
    }).encode("utf-8")
    status_label, frames = ws_exchange(host, port, ws_path, token, [outbound], args.timeout, args.max_total, verbose=True)
    print(f"[3/3] exchange finished: {status_label}", file=sys.stderr)

    print(f"\n=== assistant reply ({len(frames)} frames) ===")
    for f in frames:
        if isinstance(f, str):
            print(f, end="", flush=True)
        else:
            print(f, flush=True)
    print("\n=== end ===")
    if status_label == "done":
        return 0
    if status_label == "error":
        return 2
    if status_label == "timeout":
        return 3
    return 2


if __name__ == "__main__":
    sys.exit(main())
