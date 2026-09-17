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
from .parser import parse_team_soul, write_team_artifacts
from .runtime import MemberCaller, MockMemberCaller, TeamAgentRuntime

__all__ = [
    "MemberCaller",
    "MemberOutput",
    "MockMemberCaller",
    "TeamAgentRuntime",
    "TeamDefinition",
    "TeamMember",
    "TeamPhase",
    "TeamRunResult",
    "parse_team_soul",
    "write_team_artifacts",
]
