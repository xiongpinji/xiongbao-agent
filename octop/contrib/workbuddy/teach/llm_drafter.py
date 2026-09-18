# SPDX-License-Identifier: MIT
"""Optional LLM polish for SkillDraft (rules remain source of truth for safety).

Flow: ``draft_skill_from_recording`` → ``polish_draft_with_llm`` → human approve.
The LLM may rewrite trigger / step instructions only. Approval flags, policies,
and step kinds stay gated by the rule-based draft (or stricter).
"""

from __future__ import annotations

import json
import re
from typing import Any, Protocol

from ..team.llm import OpenAICompatCaller
from .drafter import _needs_approval
from .models import DraftStep, SkillDraft

SYSTEM_PROMPT = """你是技能草稿润色助手。输入是一份已由规则引擎生成的 SkillDraft JSON。
你只能改进 trigger 与各 step 的 instruction 文案（更清晰、可执行、中文）。
禁止增删步骤、禁止改 kind、禁止取消 requires_approval、禁止改动安全策略字段。
只输出一个 JSON 对象，不要 Markdown，字段：
{
  "trigger": "...",
  "steps": [{"index": 0, "instruction": "..."}, ...]
}
steps 数量必须与输入完全一致，index 从 0 连续。"""


class Completer(Protocol):
    def complete(self, *, system: str, user: str) -> str: ...


def _extract_json(text: str) -> dict[str, Any]:
    raw = text.strip()
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, re.DOTALL | re.IGNORECASE)
    if fence:
        raw = fence.group(1)
    else:
        start = raw.find("{")
        end = raw.rfind("}")
        if start >= 0 and end > start:
            raw = raw[start : end + 1]
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("LLM JSON root must be an object")
    return data


def _merge_polish(base: SkillDraft, patch: dict[str, Any]) -> SkillDraft:
    trigger = str(patch.get("trigger") or base.trigger).strip() or base.trigger
    patched_steps = patch.get("steps")
    new_steps: list[DraftStep] = []
    by_index: dict[int, str] = {}
    if isinstance(patched_steps, list):
        for item in patched_steps:
            if not isinstance(item, dict):
                continue
            try:
                idx = int(item.get("index"))
            except (TypeError, ValueError):
                continue
            instr = str(item.get("instruction") or "").strip()
            if instr:
                by_index[idx] = instr

    for step in base.steps:
        instruction = by_index.get(step.index, step.instruction)
        # Never loosen approval: keep base flag or re-detect from text
        needs = step.requires_approval or _needs_approval(
            step.kind, "", instruction
        )
        new_steps.append(
            DraftStep(
                index=step.index,
                kind=step.kind,
                instruction=instruction,
                requires_approval=needs,
                is_decision=step.is_decision,
                source_step_index=step.source_step_index,
            )
        )

    return SkillDraft(
        name=base.name,
        trigger=trigger,
        intent=base.intent,
        recording_id=base.recording_id,
        inputs=list(base.inputs),
        steps=new_steps,
        validations=list(base.validations),
        approvals=list(base.approvals),
        no_data_policy=base.no_data_policy,
        stale_data_policy=base.stale_data_policy,
        idempotency_notes=base.idempotency_notes,
        status="draft",  # always back to draft after polish
        created_at=base.created_at,
        source="rules+llm",
    )


def polish_draft_with_llm(
    draft: SkillDraft,
    *,
    caller: Completer | None = None,
    fallback_on_error: bool = True,
) -> SkillDraft:
    """Polish a rule-based draft. On LLM failure, return base with ``source=rules``."""
    if draft.status == "approved":
        # Polishing resets review — caller should re-approve
        pass
    llm: Completer = caller or OpenAICompatCaller(max_tokens=1024, temperature=0.2)
    user_payload = {
        "name": draft.name,
        "intent": draft.intent,
        "trigger": draft.trigger,
        "steps": [
            {
                "index": s.index,
                "kind": s.kind,
                "instruction": s.instruction,
                "requires_approval": s.requires_approval,
                "is_decision": s.is_decision,
            }
            for s in draft.steps
        ],
    }
    user = (
        "请润色下列 SkillDraft（保持步骤数量与安全标记）：\n"
        + json.dumps(user_payload, ensure_ascii=False, indent=2)
    )
    try:
        text = llm.complete(system=SYSTEM_PROMPT, user=user)
        patch = _extract_json(text)
        if "steps" in patch and isinstance(patch["steps"], list):
            if len(patch["steps"]) != len(draft.steps):
                raise ValueError(
                    f"LLM step count {len(patch['steps'])} != base {len(draft.steps)}"
                )
        return _merge_polish(draft, patch)
    except Exception:
        if not fallback_on_error:
            raise
        out = SkillDraft.from_dict(draft.to_dict())
        out.source = "rules"
        out.status = "draft"
        return out
