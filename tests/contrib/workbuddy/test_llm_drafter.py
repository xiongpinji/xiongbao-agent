# SPDX-License-Identifier: MIT
"""Tests for LLM SkillDraft polish (stub completer; no live Ollama required)."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT))

from octop.contrib.workbuddy.teach import (  # noqa: E402
    TeachRecorder,
    draft_skill_from_recording,
    polish_draft_with_llm,
)
from octop.contrib.workbuddy.teach.llm_drafter import _extract_json  # noqa: E402


class StubCompleter:
    def __init__(self, payload: dict | str, *, fail: bool = False) -> None:
        self.payload = payload
        self.fail = fail
        self.calls = 0

    def complete(self, *, system: str, user: str) -> str:
        self.calls += 1
        if self.fail:
            raise RuntimeError("llm down")
        if isinstance(self.payload, str):
            return self.payload
        return json.dumps(self.payload, ensure_ascii=False)


def _base_draft():
    rec = TeachRecorder(bot_id="b1", intent="抓取 PR 并发送飞书")
    rec.navigate("https://example/prs")
    rec.read_data("prs")
    rec.decision("非空？")
    rec.append("message", "发送到飞书", tool_name="send", target="feishu:g1")
    return draft_skill_from_recording(rec.close(), name="pr-feishu")


def test_extract_json_from_fence() -> None:
    text = '前言\n```json\n{"trigger": "x", "steps": []}\n```\n尾'
    data = _extract_json(text)
    assert data["trigger"] == "x"


def test_polish_updates_text_keeps_safety() -> None:
    base = _base_draft()
    assert base.source == "rules"
    risky = [s for s in base.steps if s.requires_approval]
    assert risky

    patch = {
        "trigger": "当用户要同步今日 PR 到飞书时启动",
        "steps": [
            {"index": s.index, "instruction": f"润色步骤{s.index}：{s.instruction}"}
            for s in base.steps
        ],
    }
    stub = StubCompleter(patch)
    out = polish_draft_with_llm(base, caller=stub, fallback_on_error=False)
    assert stub.calls == 1
    assert out.source == "rules+llm"
    assert out.status == "draft"
    assert out.trigger.startswith("当用户要同步")
    assert len(out.steps) == len(base.steps)
    for before, after in zip(base.steps, out.steps):
        assert after.kind == before.kind
        if before.requires_approval:
            assert after.requires_approval
        assert after.instruction.startswith("润色步骤")


def test_polish_rejects_step_count_mismatch_falls_back() -> None:
    base = _base_draft()
    bad = StubCompleter({"trigger": "t", "steps": [{"index": 0, "instruction": "only one"}]})
    out = polish_draft_with_llm(base, caller=bad, fallback_on_error=True)
    assert out.source == "rules"
    assert len(out.steps) == len(base.steps)


def test_polish_fallback_on_llm_error() -> None:
    base = _base_draft()
    out = polish_draft_with_llm(base, caller=StubCompleter({}, fail=True), fallback_on_error=True)
    assert out.source == "rules"
    assert out.name == base.name


def test_polish_cannot_clear_approvals_via_text_only() -> None:
    """Even if LLM omits approval hints, merge keeps base requires_approval."""
    base = _base_draft()
    patch = {
        "trigger": base.trigger,
        "steps": [{"index": s.index, "instruction": "纯描述无风险词"} for s in base.steps],
    }
    out = polish_draft_with_llm(base, caller=StubCompleter(patch), fallback_on_error=False)
    for before, after in zip(base.steps, out.steps):
        if before.requires_approval:
            assert after.requires_approval


if __name__ == "__main__":
    test_extract_json_from_fence()
    test_polish_updates_text_keeps_safety()
    test_polish_rejects_step_count_mismatch_falls_back()
    test_polish_fallback_on_llm_error()
    test_polish_cannot_clear_approvals_via_text_only()
    print("ALL LLM DRAFTER TESTS OK")
