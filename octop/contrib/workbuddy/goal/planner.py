# SPDX-License-Identifier: MIT
"""Rule-based Goal planner (optional LLM polish via ``llm_planner``)."""

from __future__ import annotations

import re

from .models import AcceptanceCriterion, GoalPlan, PlanStep

_WRITE_RE = re.compile(r"写[入到]?|保存|落盘|生成.*文件|report|报告", re.I)
_MSG_RE = re.compile(r"通知|飞书|lark|消息|发[送给]|webhook|提醒", re.I)
_READ_RE = re.compile(r"读取|抓取|打开|查看|拉取", re.I)
_FILE_RE = re.compile(
    r"([A-Za-z0-9_\-./\\]+\.(?:md|txt|json|csv))|"
    r"[「\"']([^」\"']+\.(?:md|txt|json|csv))[」\"']|"
    r"写入\s*([^\s，,。]+)"
)


def _guess_filename(goal: str) -> str:
    m = _FILE_RE.search(goal)
    if m:
        for g in m.groups():
            if g:
                name = g.strip().lstrip("/")
                if ".." in name.split("/"):
                    continue
                return name.replace("\\", "/")
    if "pr" in goal.lower():
        return "pr-summary.md"
    if "周报" in goal or "weekly" in goal.lower():
        return "weekly-report.md"
    return "goal-output.md"


def _guess_message_target(goal: str) -> str:
    if re.search(r"飞书|lark|feishu", goal, re.I):
        return "feishu:webhook"
    return "local:outbox"


def plan_goal(goal: str, *, skill_context: str = "") -> GoalPlan:
    """Compile a natural-language goal into steps + acceptance criteria.

    ``skill_context`` (optional SkillHub compose text) is embedded into the
    write artifact only — it does not change step kinds or filename heuristics.
    """
    text = (goal or "").strip()
    if not text:
        raise ValueError("goal is empty")

    want_write = bool(_WRITE_RE.search(text)) or True  # always produce an artifact
    want_msg = bool(_MSG_RE.search(text))
    want_read = bool(_READ_RE.search(text))
    filename = _guess_filename(text)
    msg_target = _guess_message_target(text)

    steps: list[PlanStep] = []
    criteria: list[AcceptanceCriterion] = []
    idx = 0

    if want_read:
        src = "notion:page/demo" if "notion" in text.lower() else "stdin"
        steps.append(
            PlanStep(
                index=idx,
                kind="read",
                instruction=f"读取来源（目标：{src}）",
            )
        )
        criteria.append(
            AcceptanceCriterion(
                id=f"c-step-{idx}",
                description=f"读取步骤 {idx} 成功",
                check="step_ok",
                step_index=idx,
            )
        )
        idx += 1

    if want_write:
        body = (
            f"# Goal output\n\n目标：{text}\n\n"
            f"（由 Goal/Craft 规则规划器自动生成）\n"
        )
        ctx = (skill_context or "").strip()
        if ctx:
            body += f"\n## Bound Skills\n\n{ctx[:4000]}\n"
        steps.append(
            PlanStep(
                index=idx,
                kind="write",
                instruction=f"写入交付物（目标：{filename}）（内容：{body}）",
                requires_approval=True,
            )
        )
        write_idx = idx
        criteria.append(
            AcceptanceCriterion(
                id="c-file-exists",
                description=f"交付文件 {filename} 存在",
                check="file_exists",
                path=filename,
            )
        )
        criteria.append(
            AcceptanceCriterion(
                id="c-file-has-goal",
                description="交付文件包含目标原文片段",
                check="file_contains",
                path=filename,
                substring=text[:40],
            )
        )
        criteria.append(
            AcceptanceCriterion(
                id=f"c-step-{write_idx}",
                description=f"写入步骤 {write_idx} 成功",
                check="step_ok",
                step_index=write_idx,
            )
        )
        idx += 1

    if want_msg:
        summary = f"Goal 完成通知：{text[:120]}"
        steps.append(
            PlanStep(
                index=idx,
                kind="message",
                instruction=f"发送通知（目标：{msg_target}）（内容：{summary}）",
                requires_approval=True,
            )
        )
        criteria.append(
            AcceptanceCriterion(
                id="c-outbox",
                description=f"outbox 含发往 {msg_target} 的消息",
                check="outbox_message",
                target=msg_target,
            )
        )
        criteria.append(
            AcceptanceCriterion(
                id=f"c-step-{idx}",
                description=f"消息步骤 {idx} 成功",
                check="step_ok",
                step_index=idx,
            )
        )
        idx += 1

    if not steps:
        steps.append(
            PlanStep(
                index=0,
                kind="write",
                instruction=f"写入交付物（目标：goal-output.md）（内容：{text}）",
                requires_approval=True,
            )
        )
        criteria.append(
            AcceptanceCriterion(
                id="c-file-exists",
                description="goal-output.md 存在",
                check="file_exists",
                path="goal-output.md",
            )
        )

    return GoalPlan(goal=text, steps=steps, criteria=criteria, source="rules")
