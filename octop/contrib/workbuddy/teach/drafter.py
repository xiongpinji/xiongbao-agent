# SPDX-License-Identifier: MIT
"""Compile TeachRecording → SkillDraft (rule-based; LLM optional later)."""

from __future__ import annotations

from .models import (
    HIGH_RISK_KINDS,
    HIGH_RISK_TOOLS,
    Approval,
    DraftStep,
    InputSpec,
    SkillDraft,
    TeachRecording,
    Validation,
)
from .recorder import TeachRecorder


def _needs_approval(kind: str, tool_name: str, summary: str) -> bool:
    blob = f"{tool_name} {summary}".lower()
    if kind in HIGH_RISK_KINDS:
        return True
    return any(t in blob for t in HIGH_RISK_TOOLS)


def draft_skill_from_recording(
    recording: TeachRecording,
    *,
    name: str | None = None,
    trigger: str | None = None,
) -> SkillDraft:
    """Turn closed recording into a reviewable SkillDraft.

    Defaults mirror Grok Bot safety: risky steps need approval; missing data aborts;
    never silently reuse stale files.
    """
    if recording.status == "recording":
        raise ValueError("close the recording before drafting")
    if not recording.steps:
        raise ValueError("recording has no steps")

    skill_name = name or TeachRecorder.suggested_skill_name(recording.intent)
    trig = trigger or f"当用户请求：{recording.intent}"

    draft_steps: list[DraftStep] = []
    approvals: list[Approval] = []
    for i, step in enumerate(recording.steps):
        approval = _needs_approval(step.kind, step.tool_name, step.summary)
        is_decision = step.kind == "decision"
        instruction = step.summary
        if step.target:
            instruction = f"{instruction}（目标：{step.target}）"
        # write/type/message need payload for LiveStepRunner parse_content
        if step.value and step.kind in {"type", "write", "message"}:
            instruction = f"{instruction}（内容：{step.value}）"
        draft_steps.append(
            DraftStep(
                index=i,
                kind=step.kind,
                instruction=instruction,
                requires_approval=approval or is_decision,
                is_decision=is_decision,
                source_step_index=step.index,
            )
        )
        if approval:
            approvals.append(
                Approval(
                    action=step.tool_name or step.kind,
                    reason=f"step {i}: {step.summary}",
                )
            )

    # Guarantee at least one explicit approval boundary when outbound-ish intent
    intent_l = recording.intent.lower()
    if not approvals and any(
        k in intent_l for k in ("发送", "发消息", "飞书", "邮件", "publish", "send")
    ):
        approvals.append(
            Approval(action="outbound", reason="intent implies external delivery")
        )
        if draft_steps:
            draft_steps[-1].requires_approval = True

    return SkillDraft(
        name=skill_name,
        trigger=trig,
        intent=recording.intent,
        recording_id=recording.id,
        inputs=[
            InputSpec(name="query", description="用户本轮请求/参数", required=True),
        ],
        steps=draft_steps,
        validations=[
            Validation(on_failure="abort_and_notify", retry=0),
            Validation(on_failure="pause_on_source_down", retry=0),
        ],
        approvals=approvals,
        no_data_policy="abort_and_notify",
        stale_data_policy="abort_do_not_reuse_yesterday",
        idempotency_notes="re-run skips completed targets when idempotent marker exists",
        status="draft",
        source="rules",
    )
