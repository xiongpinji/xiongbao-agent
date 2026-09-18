# SPDX-License-Identifier: MIT
"""Teach-by-demonstration data models (Grok Bot–inspired V2 MVP).

Recording → SkillDraft (review required) → Routine.
High-risk actions default to requiring approval.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


StepKind = Literal[
    "navigate",
    "click",
    "type",
    "scroll",
    "message",
    "tool",
    "read",
    "write",
    "decision",
    "approval",
    "other",
]

# Actions that MUST be gated before becoming a live Routine step.
HIGH_RISK_KINDS = frozenset({"write", "message", "approval"})
HIGH_RISK_TOOLS = frozenset(
    {
        "send",
        "email",
        "purchase",
        "buy",
        "delete",
        "publish",
        "deploy",
        "transfer",
        "pay",
    }
)


@dataclass
class RecordedStep:
    """One observed action during a teach session."""

    index: int
    kind: StepKind
    summary: str
    target: str = ""
    value: str = ""
    tool_name: str = ""
    ts: str = field(default_factory=lambda: _iso(_utc_now()))
    meta: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RecordedStep:
        return cls(
            index=int(data["index"]),
            kind=data.get("kind", "other"),  # type: ignore[arg-type]
            summary=str(data.get("summary") or ""),
            target=str(data.get("target") or ""),
            value=str(data.get("value") or ""),
            tool_name=str(data.get("tool_name") or ""),
            ts=str(data.get("ts") or _iso(_utc_now())),
            meta=dict(data.get("meta") or {}),
        )


@dataclass
class TeachRecording:
    """Raw teach session (≤10 minutes of visible ops)."""

    id: str
    bot_id: str
    intent: str
    steps: list[RecordedStep] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: _iso(_utc_now()))
    closed_at: str | None = None
    max_duration_sec: int = 600
    status: Literal["recording", "closed", "compiled"] = "recording"

    def duration_sec(self) -> int:
        if not self.closed_at:
            return 0
        try:
            start = datetime.fromisoformat(self.created_at)
            end = datetime.fromisoformat(self.closed_at)
            return max(0, int((end - start).total_seconds()))
        except ValueError:
            return 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "bot_id": self.bot_id,
            "intent": self.intent,
            "steps": [s.to_dict() for s in self.steps],
            "created_at": self.created_at,
            "closed_at": self.closed_at,
            "max_duration_sec": self.max_duration_sec,
            "status": self.status,
            "duration_sec": self.duration_sec(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TeachRecording:
        return cls(
            id=str(data["id"]),
            bot_id=str(data.get("bot_id") or "default"),
            intent=str(data.get("intent") or ""),
            steps=[RecordedStep.from_dict(s) for s in (data.get("steps") or [])],
            created_at=str(data.get("created_at") or _iso(_utc_now())),
            closed_at=data.get("closed_at"),
            max_duration_sec=int(data.get("max_duration_sec") or 600),
            status=data.get("status") or "recording",  # type: ignore[arg-type]
        )


@dataclass
class InputSpec:
    name: str
    description: str = ""
    required: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> InputSpec:
        return cls(
            name=str(data["name"]),
            description=str(data.get("description") or ""),
            required=bool(data.get("required", True)),
        )


@dataclass
class DraftStep:
    """Numbered skill step after drafting."""

    index: int
    kind: StepKind
    instruction: str
    requires_approval: bool = False
    is_decision: bool = False
    source_step_index: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DraftStep:
        return cls(
            index=int(data["index"]),
            kind=data.get("kind", "other"),  # type: ignore[arg-type]
            instruction=str(data.get("instruction") or ""),
            requires_approval=bool(data.get("requires_approval")),
            is_decision=bool(data.get("is_decision")),
            source_step_index=data.get("source_step_index"),
        )


@dataclass
class Validation:
    on_failure: str
    retry: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Validation:
        return cls(
            on_failure=str(data.get("on_failure") or "abort"),
            retry=int(data.get("retry") or 0),
        )


@dataclass
class Approval:
    action: str
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Approval:
        return cls(action=str(data["action"]), reason=str(data.get("reason") or ""))


@dataclass
class SkillDraft:
    """Draft skill — must be human-reviewed before becoming a Routine."""

    name: str
    trigger: str
    intent: str
    recording_id: str
    inputs: list[InputSpec] = field(default_factory=list)
    steps: list[DraftStep] = field(default_factory=list)
    validations: list[Validation] = field(default_factory=list)
    approvals: list[Approval] = field(default_factory=list)
    no_data_policy: str = "abort_and_notify"
    stale_data_policy: str = "abort_do_not_reuse_yesterday"
    idempotency_notes: str = "steps should be re-runnable; skip if target already done"
    status: Literal["draft", "approved", "rejected"] = "draft"
    source: Literal["rules", "rules+llm", "llm"] = "rules"
    created_at: str = field(default_factory=lambda: _iso(_utc_now()))

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "trigger": self.trigger,
            "intent": self.intent,
            "recording_id": self.recording_id,
            "inputs": [i.to_dict() for i in self.inputs],
            "steps": [s.to_dict() for s in self.steps],
            "validations": [v.to_dict() for v in self.validations],
            "approvals": [a.to_dict() for a in self.approvals],
            "no_data_policy": self.no_data_policy,
            "stale_data_policy": self.stale_data_policy,
            "idempotency_notes": self.idempotency_notes,
            "status": self.status,
            "source": self.source,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SkillDraft:
        return cls(
            name=str(data["name"]),
            trigger=str(data.get("trigger") or ""),
            intent=str(data.get("intent") or ""),
            recording_id=str(data.get("recording_id") or ""),
            inputs=[InputSpec.from_dict(i) for i in (data.get("inputs") or [])],
            steps=[DraftStep.from_dict(s) for s in (data.get("steps") or [])],
            validations=[Validation.from_dict(v) for v in (data.get("validations") or [])],
            approvals=[Approval.from_dict(a) for a in (data.get("approvals") or [])],
            no_data_policy=str(data.get("no_data_policy") or "abort_and_notify"),
            stale_data_policy=str(
                data.get("stale_data_policy") or "abort_do_not_reuse_yesterday"
            ),
            idempotency_notes=str(data.get("idempotency_notes") or ""),
            status=data.get("status") or "draft",  # type: ignore[arg-type]
            source=data.get("source") or "rules",  # type: ignore[arg-type]
            created_at=str(data.get("created_at") or _iso(_utc_now())),
        )
