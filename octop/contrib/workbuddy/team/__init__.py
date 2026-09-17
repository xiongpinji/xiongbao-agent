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
from .models_catalog import ModelSpec, MatchResult, match_model, pull_model
from .parser import parse_team_soul, write_team_artifacts
from .probe import ProbeResult, probe_local_llm
from .runtime import MemberCaller, MockMemberCaller, TeamAgentRuntime

__all__ = [
    "LocalLLMCaller",
    "MatchResult",
    "MemberCaller",
    "MemberOutput",
    "MockMemberCaller",
    "ModelSpec",
    "OpenAICompatCaller",
    "ProbeResult",
    "TeamAgentRuntime",
    "TeamDefinition",
    "TeamMember",
    "TeamPhase",
    "TeamRunResult",
    "match_model",
    "parse_team_soul",
    "probe_local_llm",
    "pull_model",
    "write_team_artifacts",
]
