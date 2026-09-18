# SPDX-License-Identifier: MIT
"""Teach-by-demonstration package (V2)."""

from __future__ import annotations

from .cdp_recorder import CdpTeachSession, cdp_available
from .cdp_replay import CdpReplaySession
from .drafter import draft_skill_from_recording
from .llm_drafter import polish_draft_with_llm
from .models import (
    Approval,
    DraftStep,
    InputSpec,
    RecordedStep,
    SkillDraft,
    TeachRecording,
    Validation,
)
from .recorder import TeachRecorder
from .store import TeachStore

__all__ = [
    "Approval",
    "CdpReplaySession",
    "CdpTeachSession",
    "DraftStep",
    "InputSpec",
    "RecordedStep",
    "SkillDraft",
    "TeachRecorder",
    "TeachRecording",
    "TeachStore",
    "Validation",
    "cdp_available",
    "draft_skill_from_recording",
    "polish_draft_with_llm",
]
