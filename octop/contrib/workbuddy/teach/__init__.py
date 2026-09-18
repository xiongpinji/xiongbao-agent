# SPDX-License-Identifier: MIT
"""Teach-by-demonstration package (V2)."""

from __future__ import annotations

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
    "DraftStep",
    "InputSpec",
    "RecordedStep",
    "SkillDraft",
    "TeachRecorder",
    "TeachRecording",
    "TeachStore",
    "Validation",
    "draft_skill_from_recording",
    "polish_draft_with_llm",
]
