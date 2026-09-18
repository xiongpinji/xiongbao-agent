# SPDX-License-Identifier: MIT
"""Outbox delivery log + retry for Feishu (and local) message sends.

Every outbound attempt is appended to ``<work_dir>/outbox/delivery.jsonl``.
Failed / pending rows can be retried via ``retry_deliveries``.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, TYPE_CHECKING

if TYPE_CHECKING:
    from . import FeishuConnector


def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class DeliveryRecord:
    id: str
    ts: str
    status: str  # pending | sent | failed | skipped
    target: str
    content: str
    error: str = ""
    attempts: int = 0
    connector: dict[str, Any] = field(default_factory=dict)
    work_dir: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DeliveryRecord:
        return cls(
            id=str(data.get("id") or ""),
            ts=str(data.get("ts") or ""),
            status=str(data.get("status") or "pending"),
            target=str(data.get("target") or ""),
            content=str(data.get("content") or ""),
            error=str(data.get("error") or ""),
            attempts=int(data.get("attempts") or 0),
            connector=dict(data.get("connector") or {}),
            work_dir=str(data.get("work_dir") or ""),
        )


def delivery_log_path(work_dir: Path) -> Path:
    outbox = Path(work_dir) / "outbox"
    outbox.mkdir(parents=True, exist_ok=True)
    return outbox / "delivery.jsonl"


def append_delivery(work_dir: Path, record: DeliveryRecord) -> Path:
    path = delivery_log_path(work_dir)
    record.work_dir = str(Path(work_dir))
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record.to_dict(), ensure_ascii=False) + "\n")
    return path


def load_deliveries(work_dir: Path) -> list[DeliveryRecord]:
    path = delivery_log_path(work_dir)
    if not path.is_file():
        return []
    rows: list[DeliveryRecord] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(DeliveryRecord.from_dict(json.loads(line)))
        except json.JSONDecodeError:
            continue
    return rows


def record_attempt(
    work_dir: Path,
    *,
    target: str,
    content: str,
    status: str,
    error: str = "",
    connector: dict[str, Any] | None = None,
    delivery_id: str | None = None,
    attempts: int = 1,
) -> DeliveryRecord:
    rec = DeliveryRecord(
        id=delivery_id or f"del-{uuid.uuid4().hex[:10]}",
        ts=_utc_iso(),
        status=status,
        target=target,
        content=content,
        error=error,
        attempts=attempts,
        connector=connector or {},
    )
    append_delivery(work_dir, rec)
    return rec


def _rewrite_log(work_dir: Path, rows: list[DeliveryRecord]) -> None:
    path = delivery_log_path(work_dir)
    with path.open("w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r.to_dict(), ensure_ascii=False) + "\n")


def retry_deliveries(
    work_dir: Path,
    *,
    statuses: set[str] | None = None,
    max_items: int = 50,
    feishu: FeishuConnector | None = None,
    send_fn: Callable[[str, str], Any] | None = None,
    require_outbound_flag: bool = True,
) -> dict[str, Any]:
    """Retry failed/pending Feishu deliveries; rewrite log with updated statuses.

    ``send_fn(target, content)`` may return ConnectorResult-like object with
    ``ok`` / ``error`` / ``to_dict``; default uses ``resolve_message``.
    """
    from . import resolve_message  # local import avoids circular load

    want = statuses or {"failed", "pending"}
    rows = load_deliveries(work_dir)
    # Prefer latest attempt per id
    latest: dict[str, DeliveryRecord] = {}
    for r in rows:
        latest[r.id] = r

    retried: list[dict[str, Any]] = []
    count = 0
    for did, rec in list(latest.items()):
        if rec.status not in want:
            continue
        if count >= max_items:
            break
        count += 1
        tgt = rec.target
        text = rec.content
        if send_fn is not None:
            conn = send_fn(tgt, text)
        else:
            conn = resolve_message(
                tgt,
                text,
                feishu=feishu,
                require_outbound_flag=require_outbound_flag,
            )
        if conn is None:
            new_status = "skipped"
            err = "non-feishu target; local outbox only"
            conn_dict: dict[str, Any] = {"skipped": True}
            ok = True
        else:
            ok = bool(getattr(conn, "ok", False))
            err = str(getattr(conn, "error", "") or "")
            conn_dict = conn.to_dict() if hasattr(conn, "to_dict") else dict(conn)
            new_status = "sent" if ok else "failed"

        updated = DeliveryRecord(
            id=rec.id,
            ts=_utc_iso(),
            status=new_status,
            target=rec.target,
            content=rec.content,
            error=err,
            attempts=rec.attempts + 1,
            connector=conn_dict,
            work_dir=str(Path(work_dir)),
        )
        rows.append(updated)
        latest[did] = updated
        retried.append(updated.to_dict())

    if retried:
        _rewrite_log(work_dir, rows)

    return {
        "work_dir": str(Path(work_dir)),
        "retried": len(retried),
        "items": retried,
        "ok": all(i.get("status") == "sent" or i.get("status") == "skipped" for i in retried)
        if retried
        else True,
    }
