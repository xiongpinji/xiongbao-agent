# SPDX-License-Identifier: MIT
"""WorkBuddy Bench adapter + local expert smoke suite.

Two layers:

1. **Local smoke** (always available): 50 tasks sampled from converted
   WorkBuddy experts (33 teams + 17 agents). Runs against
   ``TeamAgentRuntime`` / structural agent checks with MockMemberCaller.
2. **Official Office subset** (optional): when
   ``vendor/workbuddy-bench/datasets/wb-bench-office-v1.0/`` is present,
   tasks can be listed for the upstream Harbor harness.

Usage::

    python -S -m octop.contrib.workbuddy.bench.cli --sample 50
"""

from __future__ import annotations

from .metrics import MetricsSink, RunMetrics
from .models import BenchReport, BenchTask, TaskResult
from .runner import BenchRunner
from .sample import build_smoke_sample, default_library_root

__all__ = [
    "BenchReport",
    "BenchRunner",
    "BenchTask",
    "MetricsSink",
    "RunMetrics",
    "TaskResult",
    "build_smoke_sample",
    "default_library_root",
]
