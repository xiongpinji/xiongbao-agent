# SPDX-License-Identifier: MIT
"""TeamAgentRuntime — lead-mediated Supervisor over WorkBuddy team experts.

Design
------
WorkBuddy team experts encode the full roster + workflow inside the lead's
SOUL.md. Members are not separate expert packages. This runtime:

1. Loads / parses the roster (``team.json`` or SOUL.md).
2. Builds an execution plan (phases: parallel or sequential).
3. Invokes each member via an injectable ``MemberCaller`` (LLM / mock / dry).
4. Asks the lead caller to synthesize a final report (Supervisor pattern).

No LangGraph dependency here — the graph is a thin sequential/parallel
scheduler so it can run under ``python -S`` without Octop's full stack.
A later adapter can wrap the same plan as a LangGraph StateGraph.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from .models import MemberOutput, TeamDefinition, TeamRunResult
from .parser import parse_team_expert_dir, write_team_artifacts


@runtime_checkable
class MemberCaller(Protocol):
    """Callable that produces one member (or lead) response."""

    async def __call__(
        self,
        *,
        role: str,
        agent_id: str,
        display_name: str,
        system_prompt: str,
        user_message: str,
        context: dict[str, Any],
    ) -> str: ...


class MockMemberCaller:
    """Deterministic stub caller for tests / offline demos."""

    async def __call__(
        self,
        *,
        role: str,
        agent_id: str,
        display_name: str,
        system_prompt: str,
        user_message: str,
        context: dict[str, Any],
    ) -> str:
        phase = context.get("phase_id", "")
        if role == "lead":
            n = len(context.get("member_outputs") or [])
            return (
                f"# 圆桌综合报告（mock）\n\n"
                f"**问题**：{user_message}\n\n"
                f"**上场成员**：{n} 人（phase={phase or 'all'}）\n\n"
                f"**综合视角**：基于各成员 stub 产出的演示汇总。"
            )
        return (
            f"## {display_name}（`{agent_id}`）\n\n"
            f"- 阶段：{phase or 'n/a'}\n"
            f"- 针对问题：{user_message}\n"
            f"- 结论（mock）：按职责完成独立分析，待主理人汇编。"
        )


class TeamAgentRuntime:
    """Supervisor runtime for one team expert."""

    def __init__(
        self,
        definition: TeamDefinition,
        *,
        caller: MemberCaller | None = None,
        expert_dir: Path | None = None,
    ) -> None:
        self.definition = definition
        self.caller: MemberCaller = caller or MockMemberCaller()
        self.expert_dir = Path(expert_dir) if expert_dir else None

    @classmethod
    def from_expert_dir(
        cls,
        expert_dir: Path,
        *,
        caller: MemberCaller | None = None,
        materialize: bool = False,
    ) -> TeamAgentRuntime:
        expert_dir = Path(expert_dir)
        definition = parse_team_expert_dir(expert_dir)
        if materialize:
            write_team_artifacts(expert_dir, definition)
            definition = parse_team_expert_dir(expert_dir)
        return cls(definition, caller=caller, expert_dir=expert_dir)

    def plan(self, query: str) -> list[dict[str, Any]]:
        """Build an execution plan without invoking any model."""
        steps: list[dict[str, Any]] = []
        steps.append(
            {
                "step": "create_team",
                "lead_id": self.definition.lead_id,
                "team_name": f"{self.definition.expert_id}-session",
                "query": query,
            }
        )
        for phase in self.definition.phases:
            steps.append(
                {
                    "step": "dispatch_phase",
                    "phase_id": phase.id,
                    "phase_name": phase.name,
                    "mode": phase.mode,
                    "member_ids": list(phase.member_ids),
                }
            )
        steps.append(
            {
                "step": "synthesize",
                "lead_id": self.definition.lead_id,
                "member_count": len(self.definition.members),
            }
        )
        return steps

    def _member_prompt(self, agent_id: str) -> str:
        member = self.definition.member_by_id(agent_id)
        if member is None:
            return f"You are team member `{agent_id}`."
        if self.expert_dir is not None:
            path = self.expert_dir / "agents" / f"{agent_id}.md"
            if path.is_file():
                return path.read_text(encoding="utf-8")
        from .parser import member_system_prompt

        return member_system_prompt(member, self.definition)

    def _lead_prompt(self) -> str:
        if self.expert_dir is not None:
            soul = self.expert_dir / "SOUL.md"
            if soul.is_file():
                return soul.read_text(encoding="utf-8")
        return (
            f"You are the team lead `{self.definition.lead_id}` "
            f"({self.definition.lead_name}). Orchestrate members and synthesize."
        )

    async def _invoke_member(
        self,
        agent_id: str,
        *,
        query: str,
        phase_id: str,
        prior: list[MemberOutput],
    ) -> MemberOutput:
        member = self.definition.member_by_id(agent_id)
        display = member.display_name if member else agent_id
        specialty = member.specialty if member else ""
        user_message = (
            f"用户问题：{query}\n"
            f"本轮研究维度：{specialty or '按你的职责独立分析'}\n"
            f"产出方式：将完整 md 报告内容直接回传给主理人"
        )
        content = await self.caller(
            role="member",
            agent_id=agent_id,
            display_name=display,
            system_prompt=self._member_prompt(agent_id),
            user_message=user_message,
            context={
                "phase_id": phase_id,
                "prior_outputs": [
                    {"agent_id": o.agent_id, "content": o.content} for o in prior
                ],
            },
        )
        return MemberOutput(
            agent_id=agent_id,
            display_name=display,
            phase_id=phase_id,
            content=content,
        )

    async def run(self, query: str, *, dry_run: bool = False) -> TeamRunResult:
        """Execute the team workflow for *query*."""
        plan = self.plan(query)
        if dry_run:
            return TeamRunResult(
                team_id=self.definition.expert_id,
                query=query,
                dry_run=True,
                plan=plan,
                member_outputs=[],
                final_report=(
                    f"[dry-run] {self.definition.expert_id}: "
                    f"{len(self.definition.members)} members / "
                    f"{len(self.definition.phases)} phase(s) planned for: {query}"
                ),
            )

        outputs: list[MemberOutput] = []
        for phase in self.definition.phases:
            if phase.mode == "parallel":
                tasks = [
                    self._invoke_member(
                        mid,
                        query=query,
                        phase_id=phase.id,
                        prior=list(outputs),
                    )
                    for mid in phase.member_ids
                ]
                phase_outs = await asyncio.gather(*tasks)
                outputs.extend(phase_outs)
            else:
                for mid in phase.member_ids:
                    out = await self._invoke_member(
                        mid,
                        query=query,
                        phase_id=phase.id,
                        prior=list(outputs),
                    )
                    outputs.append(out)

        # Lead synthesis — only sees member outputs (Supervisor hub)
        dossier = "\n\n---\n\n".join(
            f"### {o.display_name} (`{o.agent_id}`)\n\n{o.content}" for o in outputs
        )
        final = await self.caller(
            role="lead",
            agent_id=self.definition.lead_id,
            display_name=self.definition.lead_name,
            system_prompt=self._lead_prompt(),
            user_message=(
                f"用户问题：{query}\n\n"
                f"以下是各成员回传，请按结果汇编规则输出综合报告：\n\n{dossier}"
            ),
            context={
                "phase_id": "synthesize",
                "member_outputs": [
                    {"agent_id": o.agent_id, "content": o.content} for o in outputs
                ],
            },
        )

        return TeamRunResult(
            team_id=self.definition.expert_id,
            query=query,
            dry_run=False,
            plan=plan,
            member_outputs=outputs,
            final_report=final,
        )

    def run_sync(self, query: str, *, dry_run: bool = False) -> TeamRunResult:
        """Sync wrapper around :meth:`run`."""
        return asyncio.run(self.run(query, dry_run=dry_run))
