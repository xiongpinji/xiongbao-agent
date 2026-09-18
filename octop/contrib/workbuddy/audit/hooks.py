# SPDX-License-Identifier: MIT
"""Audit hooks for Goal / Task / Connector (V9.15)."""

from __future__ import annotations

from typing import Any

from .log import get_audit_log
from ..goal.models import GoalRun
from ..task import TaskRecord


def audit_goal_run(run: GoalRun, *, action: str = "goal.run") -> dict[str, Any]:
    return get_audit_log().emit(
        action,
        run_id=getattr(run, "id", ""),
        status=getattr(run, "status", ""),
        goal=getattr(run, "goal", ""),
    )


def audit_task(record: TaskRecord, *, action: str = "task.update") -> dict[str, Any]:
    return get_audit_log().emit(
        action,
        task_id=record.task_id,
        status=record.status,
        title=record.title,
        mode=record.mode,
    )


def audit_connector(provider: str, *, ok: bool, target: str = "", error: str | None = None) -> dict[str, Any]:
    return get_audit_log().emit(
        "connector.send",
        provider=provider,
        ok=ok,
        target=target,
        error=error,
    )
