# SPDX-License-Identifier: MIT
"""WorkBuddy Team expert runtime (Supervisor + members).

Parses lead SOUL.md rosters into structured ``team.json``, materializes
member prompts under ``agents/``, and runs a lead-mediated Supervisor loop.
"""

from __future__ import annotations

from .models import (
    MemberOutput,
    TeamDefinition,
    TeamMember,
    TeamPhase,
    TeamRunResult,
)
from .llm import LocalLLMCaller, OpenAICompatCaller
from .parser import parse_team_soul, write_team_artifacts
from .probe import ProbeResult, probe_local_llm
from .runtime import MemberCaller, MockMemberCaller, TeamAgentRuntime

__all__ = [
    "LocalLLMCaller",
    "MemberCaller",
    "MemberOutput",
    "MockMemberCaller",
    "OpenAICompatCaller",
    "ProbeResult",
    "TeamAgentRuntime",
    "TeamDefinition",
    "TeamMember",
    "TeamPhase",
    "TeamRunResult",
    "parse_team_soul",
    "probe_local_llm",
    "write_team_artifacts",
]
