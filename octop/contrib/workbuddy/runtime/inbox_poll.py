# SPDX-License-Identifier: MIT
"""Poll China IM inbox JSONL into ChannelBridge with cursor."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..channel_bridge import ChannelBridge, BridgeResult
from ..connectors.china_im import InboxStore
from ..task import TaskStore


class InboxPoller:
    """Consume new inbox lines since last cursor offset (byte offset)."""

    def __init__(
        self,
        inbox: InboxStore | Path | str,
        bridge: ChannelBridge,
        *,
        cursor_path: Path | str | None = None,
    ) -> None:
        self.inbox = inbox if isinstance(inbox, InboxStore) else InboxStore(inbox)
        self.bridge = bridge
        default_cursor = Path(self.inbox.path).with_suffix(".cursor")
        self.cursor_path = Path(cursor_path) if cursor_path else default_cursor

    def _read_cursor(self) -> int:
        if not self.cursor_path.is_file():
            return 0
        try:
            return int(self.cursor_path.read_text(encoding="utf-8").strip() or "0")
        except ValueError:
            return 0

    def _write_cursor(self, offset: int) -> None:
        self.cursor_path.parent.mkdir(parents=True, exist_ok=True)
        self.cursor_path.write_text(str(offset), encoding="utf-8")

    def poll(self, *, limit: int = 50) -> dict[str, Any]:
        path = self.inbox.path
        if not path.is_file():
            return {"ok": True, "processed": 0, "results": [], "cursor": 0}
        offset = self._read_cursor()
        size = path.stat().st_size
        if offset > size:
            offset = 0
        results: list[dict[str, Any]] = []
        processed = 0
        with path.open("r", encoding="utf-8") as fh:
            fh.seek(offset)
            while processed < limit:
                pos_before = fh.tell()
                line = fh.readline()
                if not line:
                    break
                if not line.endswith("\n") and fh.tell() < size:
                    # incomplete line — wait for next poll
                    fh.seek(pos_before)
                    break
                text = line.strip()
                new_offset = fh.tell()
                if not text:
                    offset = new_offset
                    continue
                try:
                    row = json.loads(text)
                except json.JSONDecodeError:
                    offset = new_offset
                    continue
                provider = str(row.get("provider") or "wechat")
                body = str(row.get("text") or row.get("content") or "")
                sender = str(row.get("sender") or row.get("from") or "")
                if not body:
                    offset = new_offset
                    continue
                br: BridgeResult = self.bridge.handle_inbound(
                    provider, body, sender=sender
                )
                results.append(br.to_dict())
                processed += 1
                offset = new_offset
        self._write_cursor(offset)
        return {
            "ok": True,
            "processed": processed,
            "results": results,
            "cursor": offset,
        }


def make_default_poller(
    *,
    inbox_path: Path | str = "artifacts/china_im/inbox.jsonl",
    tasks_root: Path | str = "artifacts/tasks",
    allow: bool = False,
) -> InboxPoller:
    store = TaskStore(tasks_root)
    bridge = ChannelBridge(store, allow=allow)
    return InboxPoller(inbox_path, bridge)
