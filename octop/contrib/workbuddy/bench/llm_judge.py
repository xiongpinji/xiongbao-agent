# SPDX-License-Identifier: MIT
"""Local LLM-lite scoring for Harbor office tasks (no Docker required).

Full Harbor verification needs Docker + upstream harness. This module provides a
**subset** path: read ``instruction.md``, ask a local LLM for a structured plan
answer, then score with heuristics (+ optional LLM judge JSON).
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any, Callable

from .models import BenchTask, TaskResult

# Caller: (system, user) -> text
LLMFn = Callable[[str, str], str]

_SYSTEM = (
    "你是办公自动化评测助手。根据用户给出的任务说明，输出一份可执行的 Markdown 答题草稿。"
    "要求：分点、引用说明中的路径/术语、不要声称已修改真实文件。"
    "若任务要求写入 final_answer.md，在文末说明将写入该文件的要点即可。"
)

_JUDGE_SYSTEM = (
    "你是严格的评分员。根据「任务说明」与「模型作答」打分。"
    "只输出一行 JSON：{\"score\":0.0到1.0,\"pass\":true或false,\"reason\":\"短句\"}。"
    "评分标准：覆盖关键要求、有结构步骤、引用了说明中的关键路径或术语、未编造已执行副作用。"
)


def _tokens(text: str, *, limit: int = 40) -> list[str]:
    # Keep alnum / CJK runs of length >= 2
    parts = re.findall(r"[A-Za-z0-9_\-./]{3,}|[\u4e00-\u9fff]{2,}", text or "")
    seen: set[str] = set()
    out: list[str] = []
    for p in parts:
        key = p.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(p)
        if len(out) >= limit:
            break
    return out


def heuristic_score(instruction: str, answer: str) -> tuple[float, dict[str, bool], str]:
    """Return (score, checks, detail)."""
    ans = (answer or "").strip()
    checks = {
        "nonempty": len(ans) >= 80,
        "structured": bool(re.search(r"(^|\n)\s*([#*\-]|\d+[\.、)])", ans)),
        "mentions_artifact": "final_answer" in ans.lower() or "交付" in ans or "Markdown" in ans,
    }
    toks = _tokens(instruction, limit=24)
    hits = sum(1 for t in toks if t.lower() in ans.lower())
    checks["keyword_overlap"] = hits >= max(2, min(5, len(toks) // 6))
    score = sum(1.0 for v in checks.values() if v) / len(checks)
    detail = "; ".join(f"{k}={'Y' if v else 'N'}" for k, v in checks.items()) + f"; hits={hits}"
    return score, checks, detail


def parse_judge_json(text: str) -> dict[str, Any] | None:
    raw = (text or "").strip()
    if not raw:
        return None
    # Prefer fenced or first {...}
    m = re.search(r"\{[^{}]*\}", raw, re.S)
    if not m:
        return None
    try:
        data = json.loads(m.group(0))
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    return data


def score_office_with_llm(
    task: BenchTask,
    *,
    llm: LLMFn,
    use_judge: bool = True,
    instruction_chars: int = 3500,
    answer_chars: int = 4000,
) -> TaskResult:
    """Generate an answer then heuristic (+ optional LLM judge) score."""
    t0 = time.perf_counter()
    instruction = (task.prompt or "")[:instruction_chars]
    if not instruction.strip():
        return TaskResult(
            task_id=task.task_id,
            kind="office",
            expert_id=task.expert_id,
            passed=False,
            score=0.0,
            latency_ms=(time.perf_counter() - t0) * 1000.0,
            detail="empty instruction",
            artifacts={"mode": "llm_lite"},
        )

    user = f"任务 id: {task.expert_id}\n\n## 任务说明\n\n{instruction}\n"
    try:
        answer = llm(_SYSTEM, user)
    except Exception as exc:  # noqa: BLE001
        return TaskResult(
            task_id=task.task_id,
            kind="office",
            expert_id=task.expert_id,
            passed=False,
            score=0.0,
            latency_ms=(time.perf_counter() - t0) * 1000.0,
            detail=f"llm error: {exc}",
            artifacts={"mode": "llm_lite"},
        )

    answer = (answer or "")[:answer_chars]
    h_score, checks, h_detail = heuristic_score(instruction, answer)
    judge_score: float | None = None
    judge_pass: bool | None = None
    judge_reason = ""

    if use_judge:
        judge_user = (
            f"## 任务说明\n{instruction[:2000]}\n\n## 模型作答\n{answer[:2500]}\n"
        )
        try:
            judged = llm(_JUDGE_SYSTEM, judge_user)
            parsed = parse_judge_json(judged)
            if parsed is not None:
                judge_score = float(parsed.get("score", 0.0))
                judge_score = max(0.0, min(1.0, judge_score))
                judge_pass = bool(parsed.get("pass"))
                judge_reason = str(parsed.get("reason") or "")[:200]
        except Exception as exc:  # noqa: BLE001
            judge_reason = f"judge error: {exc}"

    if judge_score is not None:
        score = 0.45 * h_score + 0.55 * judge_score
        passed = (judge_pass if judge_pass is not None else score >= 0.55) and h_score >= 0.5
    else:
        score = h_score
        passed = h_score >= 0.75

    latency = (time.perf_counter() - t0) * 1000.0
    detail = h_detail
    if judge_score is not None:
        detail += f"; judge={judge_score:.2f} pass={judge_pass} ({judge_reason})"
    return TaskResult(
        task_id=task.task_id,
        kind="office",
        expert_id=task.expert_id,
        passed=passed,
        score=score,
        latency_ms=latency,
        detail=detail,
        artifacts={
            "mode": "llm_lite",
            "answer_chars": len(answer),
            "checks": checks,
            "judge_score": judge_score,
            "task_dir": task.meta.get("task_dir"),
        },
    )


def load_office_instruction(task_dir: Path, *, max_chars: int = 8000) -> str:
    path = Path(task_dir) / "instruction.md"
    if not path.is_file():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")[:max_chars]
