# SPDX-License-Identifier: MIT
"""CLI: build sample + run smoke bench + write metrics."""

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
        "--dry-sample-only",
        action="store_true",
        help="Only write sample JSON, do not run",
    )
    args = parser.parse_args(argv)

    library = args.library or default_library_root()
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    tasks = build_smoke_sample(library, n=args.sample)
    sample_path = out_dir / "smoke_sample.json"
    write_sample_json(tasks, sample_path)
    print(f"sample: {len(tasks)} tasks → {sample_path}")

    if args.list_office:
        office = list_office_tasks(default_office_dataset_root())
        office_path = out_dir / "office_listed.json"
        office_path.write_text(
            json.dumps(
                {
                    "count": len(office),
                    "dataset": str(default_office_dataset_root()),
                    "tasks": [t.to_dict() for t in office],
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        print(f"office listed: {len(office)} → {office_path}")

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

    # Soft gate: require ≥90% pass for smoke deliverable
    rate = report.passed / report.total if report.total else 0.0
    if rate < 0.9:
        print(f"FAIL: pass rate {rate:.1%} < 90%")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
