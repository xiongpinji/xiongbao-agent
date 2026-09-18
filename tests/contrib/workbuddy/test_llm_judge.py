# SPDX-License-Identifier: MIT
"""Unit tests for office llm-lite judge (no Ollama required)."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT))

from octop.contrib.workbuddy.bench.llm_judge import (  # noqa: E402
    heuristic_score,
    parse_judge_json,
    score_office_with_llm,
)
from octop.contrib.workbuddy.bench.models import BenchTask  # noqa: E402
from octop.contrib.workbuddy.bench.runner import BenchRunner  # noqa: E402
from octop.contrib.workbuddy.bench.sample import (  # noqa: E402
    default_office_dataset_root,
    list_office_tasks,
)


def test_heuristic_score_structured() -> None:
    instruction = (
        "请阅读 input/sample_workspace/citrinectl/ 并解释 CLI 与 Python API，"
        "将答案写入 final_answer.md。"
    )
    answer = (
        "# 作答\n\n"
        "1. CLI：查阅 docs 与 examples 下的命令说明。\n"
        "2. Python API：从 source 入口 import。\n"
        "3. 将 Markdown 要点写入 final_answer.md，不修改样例仓库。\n"
        "路径证据：docs/、source/、config/、schema/、examples/。\n"
    )
    score, checks, _ = heuristic_score(instruction, answer)
    assert checks["nonempty"]
    assert checks["structured"]
    assert checks["mentions_artifact"]
    assert score >= 0.75


def test_parse_judge_json() -> None:
    raw = '说明忽略\n{"score": 0.8, "pass": true, "reason": "覆盖关键点"}\n尾'
    data = parse_judge_json(raw)
    assert data is not None
    assert float(data["score"]) == 0.8
    assert data["pass"] is True


def test_score_office_with_fake_llm() -> None:
    task = BenchTask(
        task_id="office-demo",
        kind="office",
        expert_id="demo-task",
        prompt=(
            "只阅读 sample_workspace 下的 docs 与 source，解释 CLI options，"
            "输出 Markdown 到 final_answer.md，不要联网。"
        ),
        category="office",
        source="unit",
        meta={"task_dir": "/tmp/demo"},
    )

    def fake_llm(system: str, user: str) -> str:
        if "评分员" in system or "score" in system.lower():
            return '{"score": 0.9, "pass": true, "reason": "结构清晰"}'
        return (
            "## 计划\n\n"
            "1. 读 docs 与 source 中的 CLI options。\n"
            "2. 交叉核对 examples。\n"
            "3. 写入 final_answer.md。\n"
            f"system_len={len(system)} user_has_task={'任务' in user}\n"
        )

    result = score_office_with_llm(task, llm=fake_llm, use_judge=True)
    assert result.passed, result.detail
    assert result.score >= 0.6
    assert result.artifacts.get("mode") == "llm_lite"


def test_runner_office_llm_lite() -> None:
    task = BenchTask(
        task_id="office-unit-1",
        kind="office",
        expert_id="unit-office",
        prompt="解释 config schema，并准备 final_answer.md 大纲。",
        category="office",
        source="unit",
        meta={},
    )

    def fake_llm(system: str, user: str) -> str:
        if "评分员" in system:
            return '{"score": 0.85, "pass": true, "reason": "ok"}'
        return (
            "1. 打开 config/schema\n2. 总结字段\n3. 写入 final_answer.md Markdown\n"
            + user[:40]
        )

    report = BenchRunner(
        office_mode="llm_lite",
        office_llm=fake_llm,
        office_use_judge=True,
    ).run([task], suite="unit-office")
    assert report.passed == 1, report.to_dict()


def test_list_office_if_present() -> None:
    root = default_office_dataset_root()
    tasks = list_office_tasks(root)
    if not (root / "tasks").is_dir():
        print("SKIP list_office (dataset not extracted)")
        return
    assert len(tasks) >= 1
    assert all(t.kind == "office" for t in tasks)
    assert all(t.prompt.strip() for t in tasks[:3])


def main() -> int:
    tests = [
        test_heuristic_score_structured,
        test_parse_judge_json,
        test_score_office_with_fake_llm,
        test_runner_office_llm_lite,
        test_list_office_if_present,
    ]
    failed = 0
    for fn in tests:
        try:
            fn()
            print(f"OK  {fn.__name__}")
        except Exception as exc:  # noqa: BLE001
            failed += 1
            print(f"FAIL {fn.__name__}: {exc}")
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
