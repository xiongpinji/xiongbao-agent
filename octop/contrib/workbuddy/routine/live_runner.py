# SPDX-License-Identifier: MIT
"""Live / test step runner — real side effects under a sandboxed work dir.

Safety:
- All file writes stay under ``work_dir``
- Outbound ``message`` steps append to outbox JSONL (no silent network send unless allow_net)
- ``navigate`` / ``read`` may HTTP GET when allow_net=True
- High-risk steps still require RoutineEngine approval gates before invocation
"""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from ..teach.models import DraftStep

_TARGET_RE = re.compile(r"（目标：([^）]+)）")
_CONTENT_RE = re.compile(r"（内容：([^）]*)）")


def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_target(instruction: str) -> str:
    m = _TARGET_RE.search(instruction)
    return (m.group(1).strip() if m else "").strip()


def parse_content(instruction: str) -> str:
    m = _CONTENT_RE.search(instruction)
    return m.group(1) if m else ""


class LiveStepRunner:
    """Execute DraftStep kinds with bounded side effects."""

    def __init__(
        self,
        work_dir: Path,
        *,
        allow_net: bool = True,
        timeout_s: float = 15.0,
    ) -> None:
        self.work_dir = Path(work_dir)
        self.work_dir.mkdir(parents=True, exist_ok=True)
        self.outbox = self.work_dir / "outbox"
        self.outbox.mkdir(parents=True, exist_ok=True)
        self.files_dir = self.work_dir / "files"
        self.files_dir.mkdir(parents=True, exist_ok=True)
        self.allow_net = allow_net
        self.timeout_s = timeout_s
        self.log_path = self.work_dir / "live_steps.jsonl"

    def _log(self, row: dict[str, Any]) -> None:
        with self.log_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")

    def _safe_path(self, rel: str) -> Path:
        rel = rel.replace("\\", "/").lstrip("/")
        if ".." in rel.split("/"):
            raise ValueError(f"path escapes sandbox: {rel}")
        path = (self.files_dir / rel).resolve()
        if not str(path).startswith(str(self.files_dir.resolve())):
            raise ValueError(f"path escapes sandbox: {rel}")
        return path

    def _http_get(self, url: str) -> dict[str, Any]:
        if not self.allow_net:
            return {"ok": True, "skipped": True, "reason": "allow_net=false", "url": url}
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"}:
            return {"ok": False, "error": f"unsupported scheme: {parsed.scheme}"}
        req = urllib.request.Request(url, method="GET", headers={"User-Agent": "xiongbao-live-runner/1"})
        try:
            with urllib.request.urlopen(req, timeout=self.timeout_s) as resp:
                body = resp.read(64_000)
                return {
                    "ok": True,
                    "url": url,
                    "status": getattr(resp, "status", 200),
                    "bytes": len(body),
                    "preview": body[:200].decode("utf-8", errors="replace"),
                }
        except urllib.error.HTTPError as exc:
            return {"ok": False, "error": f"HTTP {exc.code}", "url": url}
        except urllib.error.URLError as exc:
            return {"ok": False, "error": str(exc.reason), "url": url}

    def __call__(self, step: DraftStep, *, context: dict[str, Any]) -> dict[str, Any]:
        target = parse_target(step.instruction)
        content = parse_content(step.instruction)
        mode = str(context.get("mode") or "live")
        result: dict[str, Any] = {
            "index": step.index,
            "kind": step.kind,
            "ok": True,
            "output": "",
            "target": target,
        }
        try:
            if step.kind == "navigate":
                url = target or step.instruction
                if url.startswith("http"):
                    got = self._http_get(url)
                    result["ok"] = bool(got.get("ok"))
                    result["output"] = got
                else:
                    result["output"] = {"ok": True, "note": "non-http navigate recorded", "target": url}
            elif step.kind == "read":
                src = target or "stdin"
                if src.startswith("http"):
                    got = self._http_get(src)
                    result["ok"] = bool(got.get("ok"))
                    result["output"] = got
                else:
                    path = self._safe_path(src)
                    if path.is_file():
                        text = path.read_text(encoding="utf-8")[:8000]
                        result["output"] = {"path": str(path), "chars": len(text), "preview": text[:200]}
                    else:
                        # Missing file: policy abort_and_notify → fail unless context supplies data
                        data = context.get("reads", {}).get(src)
                        if data is not None:
                            result["output"] = {"source": src, "data": data}
                        else:
                            result["ok"] = False
                            result["error"] = f"read source missing: {src}"
            elif step.kind == "write":
                rel = target or f"step-{step.index}.txt"
                path = self._safe_path(rel)
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content or step.instruction, encoding="utf-8")
                result["output"] = {"wrote": str(path), "bytes": path.stat().st_size}
            elif step.kind == "message":
                row = {
                    "ts": _utc_iso(),
                    "target": target or "default",
                    "instruction": step.instruction,
                    "mode": mode,
                    "routine_id": context.get("routine_id"),
                }
                out = self.outbox / "messages.jsonl"
                with out.open("a", encoding="utf-8") as fh:
                    fh.write(json.dumps(row, ensure_ascii=False) + "\n")
                result["output"] = {"outbox": str(out), "target": row["target"]}
            elif step.kind == "decision":
                # Caller may set context["decisions"][index] = True/False
                decisions = context.get("decisions") or {}
                ok = bool(decisions.get(step.index, decisions.get(str(step.index), True)))
                result["ok"] = ok
                result["output"] = {"decision": ok, "question": step.instruction}
                if not ok:
                    result["error"] = "decision failed — abort"
            elif step.kind in {"click", "type", "scroll"}:
                # Browser replay is optional; record intent for audit
                result["output"] = {
                    "deferred": "cdp_replay",
                    "kind": step.kind,
                    "target": target,
                    "value": content,
                    "note": "UI replay requires CDP session; marked ok for non-UI pipelines",
                }
            else:
                result["output"] = {"noop": step.kind, "instruction": step.instruction}
        except Exception as exc:  # noqa: BLE001
            result["ok"] = False
            result["error"] = str(exc)
        self._log({**result, "ts": _utc_iso()})
        return result
