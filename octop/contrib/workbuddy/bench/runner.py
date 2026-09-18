# SPDX-License-Identifier: MIT
"""Bench runner: smoke tasks against TeamAgentRuntime + agent structural checks.

Mock mode is the default (no LLM). Swap ``caller`` for a real MemberCaller
when wiring live models.

Office tasks:
- ``office_mode="placeholder"`` (default): list-only, no Harbor Docker.
- ``office_mode="llm_lite"``: local LLM answer + heuristic/judge score (no Docker).
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from ..team.runtime import MemberCaller, MockMemberCaller, TeamAgentRuntime
from .llm_judge import LLMFn, score_office_with_llm
from .metrics import MetricsSink
from .models import BenchReport, BenchTask, TaskResult

OfficeMode = Literal["placeholder", "llm_lite"]


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class BenchRunner:
    """Execute a list of BenchTask and emit observability events."""

    def __init__(
        self,
        *,
        caller: MemberCaller | None = None,
        metrics: MetricsSink | None = None,
        materialize_teams: bool = True,
        office_mode: OfficeMode = "placeholder",
        office_llm: LLMFn | None = None,
        office_use_judge: bool = True,
    ) -> None:
        self.caller: MemberCaller = caller or MockMemberCaller()
        self.metrics = metrics or MetricsSink()
        self.materialize_teams = materialize_teams
        self.office_mode: OfficeMode = office_mode
        self.office_llm = office_llm
        self.office_use_judge = office_use_judge

    def run(self, tasks: list[BenchTask], *, suite: str = "smoke-50") -> BenchReport:
        started = _utc_now()
        self.metrics.emit("bench.start", suite=suite, total=len(tasks))
        results: list[TaskResult] = []

        for task in tasks:
            t0 = time.perf_counter()
            self.metrics.emit(
                "task.start",
                task_id=task.task_id,
                kind=task.kind,
                expert_id=task.expert_id,
            )
            try:
                result = self._run_one(task)
            except Exception as exc:  # noqa: BLE001 — bench must continue
                latency = (time.perf_counter() - t0) * 1000.0
                result = TaskResult(
                    task_id=task.task_id,
                    kind=task.kind,
                    expert_id=task.expert_id,
                    passed=False,
                    score=0.0,
                    latency_ms=latency,
                    detail=f"exception: {exc}",
                )
            results.append(result)
            self.metrics.emit(
                "task.end",
                task_id=result.task_id,
                passed=result.passed,
                score=result.score,
                latency_ms=round(result.latency_ms, 2),
                detail=result.detail[:200],
            )

        passed = sum(1 for r in results if r.passed)
        failed = len(results) - passed
        avg_lat = sum(r.latency_ms for r in results) / len(results) if results else 0.0
        avg_score = sum(r.score for r in results) / len(results) if results else 0.0
        finished = _utc_now()
        report = BenchReport(
            suite=suite,
            total=len(results),
            passed=passed,
            failed=failed,
            avg_latency_ms=avg_lat,
            avg_score=avg_score,
            results=results,
            started_at=started,
            finished_at=finished,
        )
        self.metrics.emit(
            "bench.end",
            suite=suite,
            passed=passed,
            failed=failed,
            avg_score=round(avg_score, 4),
            avg_latency_ms=round(avg_lat, 2),
            wall_ms=round(self.metrics.elapsed_ms(), 2),
        )
        return report

    def _run_one(self, task: BenchTask) -> TaskResult:
        if task.kind == "team":
            return self._run_team(task)
        if task.kind == "agent":
            return self._run_agent(task)
        if task.kind == "office":
            if self.office_mode == "llm_lite":
                return self._run_office_llm_lite(task)
            return self._run_office_placeholder(task)
        return TaskResult(
            task_id=task.task_id,
            kind=task.kind,
            expert_id=task.expert_id,
            passed=False,
            score=0.0,
            latency_ms=0.0,
            detail=f"unsupported kind: {task.kind}",
        )

    def _run_team(self, task: BenchTask) -> TaskResult:
        t0 = time.perf_counter()
        expert_dir = Path(str(task.meta.get("expert_dir") or ""))
        if not expert_dir.is_dir():
            raise FileNotFoundError(f"expert_dir missing: {expert_dir}")

        rt = TeamAgentRuntime.from_expert_dir(
            expert_dir,
            caller=self.caller,
            materialize=self.materialize_teams,
        )
        dry = rt.run_sync(task.prompt, dry_run=True)
        live = rt.run_sync(task.prompt, dry_run=False)
        latency = (time.perf_counter() - t0) * 1000.0

        checks = {
            "has_members": len(rt.definition.members) >= 1,
            "has_plan_steps": len(dry.plan) >= 2,
            "member_outputs": len(live.member_outputs) >= 1,
            "final_report": bool(live.final_report and len(live.final_report) > 20),
        }
        score = sum(1.0 for v in checks.values() if v) / len(checks)
        passed = score >= 0.75
        return TaskResult(
            task_id=task.task_id,
            kind="team",
            expert_id=task.expert_id,
            passed=passed,
            score=score,
            latency_ms=latency,
            detail="; ".join(f"{k}={'Y' if v else 'N'}" for k, v in checks.items()),
            artifacts={
                "members": len(rt.definition.members),
                "plan_steps": len(dry.plan),
                "outputs": len(live.member_outputs),
                "orchestration": rt.definition.orchestration,
            },
        )

    def _run_agent(self, task: BenchTask) -> TaskResult:
        t0 = time.perf_counter()
        expert_dir = Path(str(task.meta.get("expert_dir") or ""))
        soul = expert_dir / "SOUL.md"
        manifest = expert_dir / "manifest.json"
        checks = {
            "manifest": manifest.is_file(),
            "soul": soul.is_file() and soul.stat().st_size > 200,
            "prompt_nonempty": bool(task.prompt and len(task.prompt) > 8),
        }
        # Light content signal: SOUL should mention role / 你是 / You are
        if soul.is_file():
            text = soul.read_text(encoding="utf-8", errors="replace")[:4000]
            checks["soul_role_signal"] = any(
                s in text for s in ("你是", "You are", "角色", "Role", "# ")
            )
        else:
            checks["soul_role_signal"] = False

        latency = (time.perf_counter() - t0) * 1000.0
        score = sum(1.0 for v in checks.values() if v) / len(checks)
        passed = score >= 0.75
        return TaskResult(
            task_id=task.task_id,
            kind="agent",
            expert_id=task.expert_id,
            passed=passed,
            score=score,
            latency_ms=latency,
            detail="; ".join(f"{k}={'Y' if v else 'N'}" for k, v in checks.items()),
            artifacts={"soul_bytes": soul.stat().st_size if soul.is_file() else 0},
        )

    def _run_office_placeholder(self, task: BenchTask) -> TaskResult:
        """Official Office tasks need Docker+Harbor; mark present-but-not-executed."""
        task_dir = Path(str(task.meta.get("task_dir") or ""))
        present = task_dir.is_dir() and (task_dir / "instruction.md").is_file()
        return TaskResult(
            task_id=task.task_id,
            kind="office",
            expert_id=task.expert_id,
            passed=False,
            score=0.0,
            latency_ms=0.0,
            detail=(
                "office task listed but not executed "
                "(use --office --live-llm for llm_lite, or full Harbor+Docker)"
                if present
                else "office task directory missing"
            ),
            artifacts={"listed_only": True, "present": present, "mode": "placeholder"},
        )

    def _run_office_llm_lite(self, task: BenchTask) -> TaskResult:
        """Local LLM-lite scoring without Docker Harbor."""
        llm = self.office_llm
        if llm is None:
            return TaskResult(
                task_id=task.task_id,
                kind="office",
                expert_id=task.expert_id,
                passed=False,
                score=0.0,
                latency_ms=0.0,
                detail="office_mode=llm_lite but office_llm is None",
                artifacts={"mode": "llm_lite"},
            )
        return score_office_with_llm(
            task,
            llm=llm,
            use_judge=self.office_use_judge,
        )
