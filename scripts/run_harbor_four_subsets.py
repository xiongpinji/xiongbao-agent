# SPDX-License-Identifier: MIT
"""Run Harbor live scores across four WorkBuddy Bench subsets.

Default: smoke (first 1 task each). Pass --full for all tasks (very long).

Usage:
  set PYTHONPATH=.
  python -S scripts/run_harbor_four_subsets.py
  python -S scripts/run_harbor_four_subsets.py --full
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

SMOKE_JOBS = [
    "local-openai-cbc-office-smoke",
    "local-openai-cbc-code-smoke",
    "local-openai-cbc-web-smoke",
    "local-openai-cbc-sec-smoke",
]
FULL_JOBS = [
    "local-openai-cbc-office-full",
    "local-openai-cbc-code-full",
    "local-openai-cbc-web-full",
    "local-openai-cbc-sec-full",
]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--full", action="store_true", help="Run all tasks in each subset")
    parser.add_argument("--timeout", type=float, default=0.0, help="Per-job timeout seconds (0=auto)")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    os.environ.setdefault("AUTO_BUILD_HARNESS_MOUNT", "1")
    # Prefer short Windows junction/subst + short stage root (MAX_PATH)
    if not os.environ.get("WB_BENCH_ROOT"):
        for candidate in (Path(r"W:\\"), Path(r"D:\wbbench"), Path("/wbbench")):
            if candidate.is_dir() and (candidate / "scripts" / "run.sh").is_file():
                os.environ["WB_BENCH_ROOT"] = str(candidate)
                break
    if not os.environ.get("WB_STAGE_ROOT"):
        stage = Path(r"C:\wbstage")
        try:
            stage.mkdir(parents=True, exist_ok=True)
            os.environ["WB_STAGE_ROOT"] = str(stage)
        except OSError:
            pass
    if os.environ.get("WB_LLM_BASE_URL") and not os.environ.get("OPENAI_BASE_URL"):
        os.environ["OPENAI_BASE_URL"] = os.environ["WB_LLM_BASE_URL"]
    if os.environ.get("WB_LLM_MODEL") and not os.environ.get("OPENAI_MODEL"):
        os.environ["OPENAI_MODEL"] = os.environ["WB_LLM_MODEL"]

    # Ensure harbor.exe is discoverable on Windows
    from octop.contrib.workbuddy.bench.harbor import harbor_score_entry, venv_python

    py = venv_python()
    if py is not None:
        scripts = str(py.parent)
        path = os.environ.get("PATH") or ""
        if scripts not in path.split(os.pathsep):
            os.environ["PATH"] = scripts + os.pathsep + path

    jobs = FULL_JOBS if args.full else SMOKE_JOBS
    # smoke ~3–10 min/job; full subsets can take many hours
    per_timeout = args.timeout or (7200.0 if args.full else 1800.0)
    out_dir = ROOT / "artifacts" / "harbor"
    out_dir.mkdir(parents=True, exist_ok=True)
    summary: list[dict] = []
    t_all = time.time()

    for job in jobs:
        print(f"\n=== {job} (timeout={per_timeout}s dry={args.dry_run}) ===", flush=True)
        t0 = time.time()
        result = harbor_score_entry(job=job, dry_run=args.dry_run, timeout=per_timeout)
        result["elapsed_sec"] = round(time.time() - t0, 1)
        result["job"] = job
        (out_dir / f"{job}.json").write_text(
            json.dumps(result, indent=2, ensure_ascii=False)[:200000],
            encoding="utf-8",
        )
        row = {
            "job": job,
            "ok": result.get("ok"),
            "returncode": result.get("returncode"),
            "elapsed_sec": result.get("elapsed_sec"),
            "mode": result.get("mode"),
            "error": (result.get("error") or "")[:200],
        }
        summary.append(row)
        print(json.dumps(row, ensure_ascii=False), flush=True)

    report = {
        "full": bool(args.full),
        "jobs": summary,
        "all_ok": all(bool(r.get("ok")) for r in summary),
        "total_elapsed_sec": round(time.time() - t_all, 1),
    }
    report_path = out_dir / ("four_subsets_full.json" if args.full else "four_subsets_smoke.json")
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    # Sanitized copy for docs (committed separately if needed)
    print("\nREPORT", json.dumps(report, ensure_ascii=False), flush=True)
    return 0 if report["all_ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
