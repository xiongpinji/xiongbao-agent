# SPDX-License-Identifier: MIT
"""Safety gates for Routine execution."""

from __future__ import annotations

from ..teach.models import SkillDraft


class SafetyError(RuntimeError):
    """Raised when a routine would violate safety policy."""


def assert_draft_approved(draft: SkillDraft) -> None:
    if draft.status != "approved":
        raise SafetyError(
            f"skill {draft.name!r} status={draft.status}; approve before creating Routine"
        )


def assert_no_stale_reuse(policy: str) -> None:
    """Stale data must not silently fall back to yesterday's file."""
    if "reuse" in policy.lower() and "do_not" not in policy.lower():
        raise SafetyError(f"unsafe stale_data_policy: {policy}")


def pending_approvals(draft: SkillDraft, granted: set[str]) -> list[str]:
    needed: list[str] = []
    for step in draft.steps:
        if not step.requires_approval:
            continue
        key = f"step:{step.index}"
        if key not in granted and step.kind not in granted:
            needed.append(key)
    for ap in draft.approvals:
        if ap.action not in granted and f"action:{ap.action}" not in granted:
            needed.append(f"action:{ap.action}")
    # unique preserve order
    seen: set[str] = set()
    out: list[str] = []
    for n in needed:
        if n not in seen:
            seen.add(n)
            out.append(n)
    return out
