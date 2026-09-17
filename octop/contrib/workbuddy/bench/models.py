# SPDX-License-Identifier: MIT
"""Bench task / result data models."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal


TaskKind = Literal["team", "agent", "office"]


@dataclass
class BenchTask:
    """One evaluation unit."""

    task_id: str
    kind: TaskKind
    expert_id: str
    prompt: str
    category: str = ""
    source: str = "smoke"
    meta: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class TaskResult:
    """Outcome of running one BenchTask."""

    task_id: str
    kind: TaskKind
    expert_id: str
    passed: bool
    score: float
    latency_ms: float
    detail: str = ""
    artifacts: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class BenchReport:
    """Aggregate report for a bench run."""

    suite: str
    total: int
    passed: int
    failed: int
    avg_latency_ms: float
    avg_score: float
    results: list[TaskResult] = field(default_factory=list)
    started_at: str = ""
    finished_at: str = ""

    def summary(self) -> str:
        rate = (100.0 * self.passed / self.total) if self.total else 0.0
        return (
            f"BenchReport[{self.suite}]: {self.passed}/{self.total} passed "
            f"({rate:.1f}%) avg_score={self.avg_score:.3f} "
            f"avg_latency={self.avg_latency_ms:.1f}ms"
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "suite": self.suite,
            "total": self.total,
            "passed": self.passed,
            "failed": self.failed,
            "avg_latency_ms": self.avg_latency_ms,
            "avg_score": self.avg_score,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "results": [r.to_dict() for r in self.results],
        }
