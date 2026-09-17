"""CLI for running the WorkBuddy converter."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .converter import WorkBuddyConverter


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Convert WorkBuddy experts → Octop library")
    parser.add_argument(
        "--vendor",
        type=Path,
        default=Path("vendor"),
        help="Path to vendor/ root (default: vendor)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("src/octop/infra/agents/experts/library"),
        help="Path to Octop experts/library/ (default: src/octop/infra/agents/experts/library)",
    )
    parser.add_argument(
        "--kind",
        choices=["agent", "team", "plugin"],
        default=None,
        help="Only convert experts of this kind",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Compute results but do not write files",
    )
    parser.add_argument(
        "--fail-on-missing",
        action="store_true",
        help="Treat missing prompt files as errors",
    )
    args = parser.parse_args(argv)

    cvt = WorkBuddyConverter(
        vendor_root=args.vendor,
        octop_root=args.output,
        skip_missing=not args.fail_on_missing,
        dry_run=args.dry_run,
    )

    report = cvt.batch_convert(filter_kind=args.kind)

    print(report.summary())
    failures = report.failed_results()
    if failures:
        print(f"\nFailed: {len(failures)}")
        for f in failures[:10]:
            print(f"  {f.expert_id}: {f.error}")
    return 0 if report.failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
