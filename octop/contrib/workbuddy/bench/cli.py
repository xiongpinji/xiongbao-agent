# SPDX-License-Identifier: MIT
"""CLI: build sample + run smoke / office llm-lite bench + write metrics."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .metrics import MetricsSink
from .runner import BenchRunner
from .sample import (
    build_smoke_sample,
    default_library_root,
    default_office_dataset_root,
    list_office_tasks,
    write_sample_json,
)


def _build_office_llm(*, use_judge: bool):
    from ..team.llm import OpenAICompatCaller

    caller = OpenAICompatCaller(max_tokens=1024, temperature=0.2)

    def llm(system: str, user: str) -> str:
        return caller.complete(system=system, user=user)

    return llm


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="WorkBuddy smoke / office bench runner")
    parser.add_argument("--sample", type=int, default=50, help="Smoke sample size (default 50)")
    parser.add_argument(
        "--library",
        type=Path,
        default=None,
        help="Expert library root (default: octop/.../experts/library)",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path("artifacts/bench"),
        help="Output directory for sample/metrics/report",
    )
    parser.add_argument(
        "--list-office",
        action="store_true",
        help="Also list official office tasks if dataset present",
    )
    parser.add_argument(
        "--office",
        action="store_true",
        help="Run office tasks instead of (or after listing) smoke sample",
    )
    parser.add_argument(
        "--live-llm",
        action="store_true",
        help="With --office: score via local LLM lite (needs Ollama / WB_LLM_*)",
    )
    parser.add_argument(
        "--no-judge",
        action="store_true",
        help="With --office --live-llm: skip second LLM judge call",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Limit office tasks (0 = all listed)",
    )
    parser.add_argument(
        "--pass-rate",
        type=float,
        default=0.9,
        help="Minimum pass rate gate (default 0.9; office llm-lite often lower)",
    )
    parser.add_argument(
        "--dry-sample-only",
        action="store_true",
        help="Only write sample JSON, do not run",
    )
    args = parser.parse_args(argv)

    library = args.library or default_library_root()
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    office_root = default_office_dataset_root()
    office = list_office_tasks(office_root)
    if args.limit and args.limit > 0:
        office = office[: args.limit]

    if args.list_office or args.office:
        office_path = out_dir / "office_listed.json"
        office_path.write_text(
            json.dumps(
                {
                    "count": len(office),
                    "dataset": str(office_root),
                    "tasks": [t.to_dict() for t in office],
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        print(f"office listed: {len(office)} → {office_path}")

    if args.office:
        if not office:
            print(f"FAIL: no office tasks under {office_root}")
            print("Hint: powershell -File scripts/fetch_office_dataset.ps1")
            return 1
        if args.dry_sample_only:
            return 0

        metrics_path = out_dir / "office_metrics.jsonl"
        sink = MetricsSink(metrics_path)
        if args.live_llm:
            llm = _build_office_llm(use_judge=not args.no_judge)
            runner = BenchRunner(
                metrics=sink,
                office_mode="llm_lite",
                office_llm=llm,
                office_use_judge=not args.no_judge,
            )
            suite = f"office-llm-lite-{len(office)}"
        else:
            runner = BenchRunner(metrics=sink, office_mode="placeholder")
            suite = f"office-list-{len(office)}"

        report = runner.run(office, suite=suite)
        report_path = out_dir / "office_report.json"
        sink.write_summary(report_path, report.to_dict())
        print(report.summary())
        print(f"metrics: {metrics_path}")
        print(f"report:  {report_path}")

        if not args.live_llm:
            # Placeholder listing is informational — always exit 0 if tasks present
            return 0

        rate = report.passed / report.total if report.total else 0.0
        gate = float(args.pass_rate)
        if rate < gate:
            print(f"FAIL: pass rate {rate:.1%} < {gate:.0%}")
            return 1
        return 0

    tasks = build_smoke_sample(library, n=args.sample)
    sample_path = out_dir / "smoke_sample.json"
    write_sample_json(tasks, sample_path)
    print(f"sample: {len(tasks)} tasks → {sample_path}")

    if args.dry_sample_only:
        return 0 if len(tasks) == args.sample or len(tasks) > 0 else 1

    metrics_path = out_dir / "metrics.jsonl"
    sink = MetricsSink(metrics_path)
    runner = BenchRunner(metrics=sink)
    report = runner.run(tasks, suite=f"smoke-{len(tasks)}")

    report_path = out_dir / "report.json"
    sink.write_summary(report_path, report.to_dict())
    print(report.summary())
    print(f"metrics: {metrics_path}")
    print(f"report:  {report_path}")

    rate = report.passed / report.total if report.total else 0.0
    gate = float(args.pass_rate)
    if rate < gate:
        print(f"FAIL: pass rate {rate:.1%} < {gate:.0%}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
