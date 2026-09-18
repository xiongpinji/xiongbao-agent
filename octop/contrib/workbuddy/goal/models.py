# SPDX-License-Identifier: MIT
"""Goal / Craft data models — plan → execute → accept."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal


def _iso() -> str:
    return datetime.now(timezone.utc).isoformat()


CheckKind = Literal[
    "file_exists",
    "file_contains",
    "outbox_message",
    "step_ok",
    "always",
]

StepKind = Literal["write", "message", "read", "navigate", "decision", "other"]


@dataclass
class AcceptanceCriterion:
    """One verifiable acceptance item (WorkBuddy「验收员」最小单元)."""

    id: str
    description: str
    check: CheckKind
    path: str = ""
    substring: str = ""
    target: str = ""
    step_index: int | None = None
    required: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AcceptanceCriterion:
        return cls(
            id=str(data["id"]),
            description=str(data.get("description") or ""),
            check=data.get("check", "always"),  # type: ignore[arg-type]
            path=str(data.get("path") or ""),
            substring=str(data.get("substring") or ""),
            target=str(data.get("target") or ""),
            step_index=data.get("step_index"),
            required=bool(data.get("required", True)),
        )


@dataclass
class PlanStep:
    index: int
    kind: StepKind
    instruction: str
    requires_approval: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PlanStep:
        return cls(
            index=int(data["index"]),
            kind=data.get("kind", "other"),  # type: ignore[arg-type]
            instruction=str(data.get("instruction") or ""),
            requires_approval=bool(data.get("requires_approval")),
        )


@dataclass
class GoalPlan:
    goal: str
    steps: list[PlanStep]
    criteria: list[AcceptanceCriterion]
    source: Literal["rules", "rules+llm"] = "rules"
    created_at: str = field(default_factory=_iso)

    def to_dict(self) -> dict[str, Any]:
        return {
            "goal": self.goal,
            "steps": [s.to_dict() for s in self.steps],
            "criteria": [c.to_dict() for c in self.criteria],
            "source": self.source,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> GoalPlan:
        return cls(
            goal=str(data.get("goal") or ""),
            steps=[PlanStep.from_dict(s) for s in data.get("steps") or []],
            criteria=[AcceptanceCriterion.from_dict(c) for c in data.get("criteria") or []],
            source=data.get("source", "rules"),  # type: ignore[arg-type]
            created_at=str(data.get("created_at") or _iso()),
        )


@dataclass
class CriterionResult:
    criterion_id: str
    ok: bool
    detail: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class GoalRun:
    id: str
    goal: str
    plan: GoalPlan
    status: Literal["planned", "running", "accepted", "rejected", "error"] = "planned"
    step_results: list[dict[str, Any]] = field(default_factory=list)
    accept_results: list[CriterionResult] = field(default_factory=list)
    retries: int = 0
    error: str = ""
    work_dir: str = ""
    created_at: str = field(default_factory=_iso)
    finished_at: str | None = None

    @property
    def ok(self) -> bool:
        return self.status == "accepted"

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "goal": self.goal,
            "plan": self.plan.to_dict(),
            "status": self.status,
            "step_results": self.step_results,
            "accept_results": [r.to_dict() for r in self.accept_results],
            "retries": self.retries,
            "error": self.error,
            "work_dir": self.work_dir,
            "created_at": self.created_at,
            "finished_at": self.finished_at,
            "ok": self.ok,
        }
