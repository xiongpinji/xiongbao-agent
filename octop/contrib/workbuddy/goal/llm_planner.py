# SPDX-License-Identifier: MIT
"""Optional LLM polish for GoalPlan (rules remain the structural source of truth).

Flow: ``plan_goal`` → ``polish_plan_with_llm`` → execute.
The LLM may rewrite step ``instruction`` and criterion ``description`` only.
Kinds, checks, paths, targets, step_index, and ``requires_approval`` stay gated.
Write/message must keep ``（目标：…）（内容：…）`` markers for LiveStepRunner.
"""

from __future__ import annotations

import json
import re
from typing import Any, Protocol

from ..team.llm import OpenAICompatCaller
from .models import AcceptanceCriterion, GoalPlan, PlanStep

SYSTEM_PROMPT = """你是 Goal 规划润色助手。输入是规则引擎已生成的 GoalPlan JSON。
你只能改进 steps[].instruction 与 criteria[].description（更清晰、可执行、中文）。
禁止增删步骤或验收项；禁止改 kind / check / path / substring / target / step_index；
禁止把 requires_approval 从 true 改为 false。
write / message 步骤的 instruction 必须保留「（目标：…）」与「（内容：…）」标记，可润色括号内正文。
只输出一个 JSON 对象，不要 Markdown：
{
  "steps": [{"index": 0, "instruction": "..."}, ...],
  "criteria": [{"id": "c-file-exists", "description": "..."}, ...]
}
steps / criteria 数量必须与输入完全一致。"""


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


def _has_runner_markers(kind: str, instruction: str) -> bool:
    if kind not in ("write", "message"):
        return True
    return "（目标：" in instruction and "（内容：" in instruction


def _merge_polish(base: GoalPlan, patch: dict[str, Any]) -> GoalPlan:
    by_index: dict[int, str] = {}
    patched_steps = patch.get("steps")
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

    new_steps: list[PlanStep] = []
    for step in base.steps:
        instruction = by_index.get(step.index, step.instruction)
        if not _has_runner_markers(step.kind, instruction):
            instruction = step.instruction
        new_steps.append(
            PlanStep(
                index=step.index,
                kind=step.kind,
                instruction=instruction,
                requires_approval=step.requires_approval,
            )
        )

    by_id: dict[str, str] = {}
    patched_criteria = patch.get("criteria")
    if isinstance(patched_criteria, list):
        for item in patched_criteria:
            if not isinstance(item, dict):
                continue
            cid = str(item.get("id") or "").strip()
            desc = str(item.get("description") or "").strip()
            if cid and desc:
                by_id[cid] = desc

    new_criteria: list[AcceptanceCriterion] = []
    for crit in base.criteria:
        new_criteria.append(
            AcceptanceCriterion(
                id=crit.id,
                description=by_id.get(crit.id, crit.description),
                check=crit.check,
                path=crit.path,
                substring=crit.substring,
                target=crit.target,
                step_index=crit.step_index,
                required=crit.required,
            )
        )

    return GoalPlan(
        goal=base.goal,
        steps=new_steps,
        criteria=new_criteria,
        source="rules+llm",
        created_at=base.created_at,
    )


def polish_plan_with_llm(
    plan: GoalPlan,
    *,
    caller: Completer | None = None,
    fallback_on_error: bool = True,
) -> GoalPlan:
    """Polish a rule-based plan. On LLM failure, return base with ``source=rules``."""
    llm: Completer = caller or OpenAICompatCaller(max_tokens=1024, temperature=0.2)
    user_payload = {
        "goal": plan.goal,
        "steps": [s.to_dict() for s in plan.steps],
        "criteria": [c.to_dict() for c in plan.criteria],
    }
    user = (
        "请润色下列 GoalPlan（保持步骤/验收数量与安全标记）：\n"
        + json.dumps(user_payload, ensure_ascii=False, indent=2)
    )
    try:
        text = llm.complete(system=SYSTEM_PROMPT, user=user)
        patch = _extract_json(text)
        if "steps" in patch and isinstance(patch["steps"], list):
            if len(patch["steps"]) != len(plan.steps):
                raise ValueError(
                    f"LLM step count {len(patch['steps'])} != base {len(plan.steps)}"
                )
        if "criteria" in patch and isinstance(patch["criteria"], list):
            if len(patch["criteria"]) != len(plan.criteria):
                raise ValueError(
                    f"LLM criteria count {len(patch['criteria'])} != base {len(plan.criteria)}"
                )
        return _merge_polish(plan, patch)
    except Exception:
        if not fallback_on_error:
            raise
        out = GoalPlan.from_dict(plan.to_dict())
        out.source = "rules"
        return out
