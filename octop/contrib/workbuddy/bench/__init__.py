# SPDX-License-Identifier: MIT
"""WorkBuddy Bench adapter + local expert smoke suite.

Two layers:

1. **Local smoke** (always available): 50 tasks sampled from converted
   WorkBuddy experts (33 teams + 17 agents). Runs against
   ``TeamAgentRuntime`` / structural agent checks with MockMemberCaller.
2. **Official Office subset** (optional): when
   ``vendor/workbuddy-bench/datasets/wb-bench-office-v1.0/`` is present,
   tasks can be listed, or scored with **llm_lite** (local LLM, no Docker).
   Full Harbor Docker scoring remains upstream-only.

Usage::

    python -S -m octop.contrib.workbuddy.bench.cli --sample 50
    python -S -m octop.contrib.workbuddy.bench.cli --office --list-office --dry-sample-only
    python -S -m octop.contrib.workbuddy.bench.cli --office --live-llm --limit 3 --pass-rate 0.3
"""

from __future__ import annotations

from .llm_judge import heuristic_score, parse_judge_json, score_office_with_llm
from .metrics import MetricsSink, RunMetrics
from .models import BenchReport, BenchTask, TaskResult
from .runner import BenchRunner
from .sample import build_smoke_sample, default_library_root, list_office_tasks

__all__ = [
    "BenchReport",
    "BenchRunner",
    "BenchTask",
    "MetricsSink",
    "RunMetrics",
    "TaskResult",
    "build_smoke_sample",
    "default_library_root",
    "heuristic_score",
    "list_office_tasks",
    "parse_judge_json",
    "score_office_with_llm",
]
