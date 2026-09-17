# SPDX-License-Identifier: MIT
"""Data models for Team expert runtime."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal


OrchestrationMode = Literal["roundtable", "phased"]
PhaseMode = Literal["parallel", "sequential"]


@dataclass(frozen=True)
class TeamMember:
    """One specialist scheduled by the team lead."""

    agent_id: str
    display_name: str
    specialty: str = ""
    phase: str = "roundtable"
    mode: PhaseMode = "parallel"
    alias: str = ""
    emoji: str = ""
    typical_query: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class TeamPhase:
    """One execution stage (parallel or sequential)."""

    id: str
    name: str
    mode: PhaseMode
    member_ids: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "mode": self.mode,
            "member_ids": list(self.member_ids),
        }


@dataclass
class TeamDefinition:
    """Structured roster extracted from a team expert SOUL.md."""

    expert_id: str
    lead_id: str
    lead_name: str
    members: list[TeamMember] = field(default_factory=list)
    phases: list[TeamPhase] = field(default_factory=list)
    orchestration: OrchestrationMode = "roundtable"
    source: str = ""

    def member_by_id(self, agent_id: str) -> TeamMember | None:
        for m in self.members:
            if m.agent_id == agent_id:
                return m
        return None

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "expert_id": self.expert_id,
            "lead_id": self.lead_id,
            "lead_name": self.lead_name,
            "orchestration": self.orchestration,
            "source": self.source,
            "members": [m.to_dict() for m in self.members],
            "phases": [p.to_dict() for p in self.phases],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TeamDefinition:
        members = [
            TeamMember(
                agent_id=str(m["agent_id"]),
                display_name=str(m.get("display_name") or m["agent_id"]),
                specialty=str(m.get("specialty") or ""),
                phase=str(m.get("phase") or "roundtable"),
                mode=m.get("mode") or "parallel",  # type: ignore[arg-type]
                alias=str(m.get("alias") or ""),
                emoji=str(m.get("emoji") or ""),
                typical_query=str(m.get("typical_query") or ""),
            )
            for m in data.get("members", [])
        ]
        phases = [
            TeamPhase(
                id=str(p["id"]),
                name=str(p.get("name") or p["id"]),
                mode=p.get("mode") or "parallel",  # type: ignore[arg-type]
                member_ids=tuple(p.get("member_ids") or []),
            )
            for p in data.get("phases", [])
        ]
        return cls(
            expert_id=str(data.get("expert_id") or ""),
            lead_id=str(data.get("lead_id") or ""),
            lead_name=str(data.get("lead_name") or ""),
            members=members,
            phases=phases,
            orchestration=data.get("orchestration") or "roundtable",  # type: ignore[arg-type]
            source=str(data.get("source") or ""),
        )


@dataclass
class MemberOutput:
    """One member's contribution for a run."""

    agent_id: str
    display_name: str
    phase_id: str
    content: str


@dataclass
class TeamRunResult:
    """Outcome of a TeamAgentRuntime.run() call."""

    team_id: str
    query: str
    dry_run: bool
    plan: list[dict[str, Any]]
    member_outputs: list[MemberOutput] = field(default_factory=list)
    final_report: str = ""

    def summary(self) -> str:
        n = len(self.member_outputs)
        mode = "dry-run" if self.dry_run else "live"
        return (
            f"TeamRunResult[{self.team_id}] {mode}: "
            f"{len(self.plan)} plan step(s), {n} member output(s)"
        )
