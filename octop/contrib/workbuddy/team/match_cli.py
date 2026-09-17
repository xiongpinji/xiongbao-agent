# SPDX-License-Identifier: MIT
"""CLI: match requirement profile → downloadable Ollama model → optional pull.

Examples::

    python -S -m octop.contrib.workbuddy.team.match_cli --profile team
    python -S -m octop.contrib.workbuddy.team.match_cli --profile team-full --pull
    python -S -m octop.contrib.workbuddy.team.match_cli --list
"""

from __future__ import annotations

import argparse
import json
import sys

from .models_catalog import (
    catalog_json,
    detect_host,
    match_model,
    pull_model,
)
from .probe import probe_local_llm


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Match & download local LLM by profile")
    parser.add_argument(
        "--profile",
        choices=["smoke", "team", "team-full", "strong"],
        default="team",
        help="Requirement profile (default: team)",
    )
    parser.add_argument("--vram-gb", type=float, default=None, help="VRAM hint for matching")
    parser.add_argument("--pull", action="store_true", help="ollama pull the recommended model")
    parser.add_argument("--list", action="store_true", help="Print catalog and exit")
    parser.add_argument(
        "--out",
        default="artifacts/live_team/model_match.json",
        help="Write match result JSON",
    )
    args = parser.parse_args(argv)

    if args.list:
        print(catalog_json())
        return 0

    probe = probe_local_llm()
    installed = probe.models if probe.ok else []
    if args.vram_gb is not None:
        import os

        os.environ["WB_LLM_VRAM_GB"] = str(args.vram_gb)

    host = detect_host(ollama_models=installed)
    if args.vram_gb is not None:
        host.vram_gb = args.vram_gb
    elif host.vram_gb is None:
        # Machine previously reported ~4GB AMD 8060S — safe default hint
        host.vram_gb = 4.0

    match = match_model(args.profile, host=host)  # type: ignore[arg-type]
    payload = {
        "probe": probe.to_dict(),
        "host": {
            "free_disk_gb": round(host.free_disk_gb, 2),
            "vram_gb": host.vram_gb,
            "installed": host.installed,
        },
        "match": match.to_dict(),
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))

    out_path = args.out
    try:
        from pathlib import Path

        p = Path(out_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"wrote {p}")
    except OSError as exc:
        print(f"warn: could not write {out_path}: {exc}", file=sys.stderr)

    if not match.recommended:
        print("FAIL: no recommended model", file=sys.stderr)
        return 2

    print(f"RECOMMENDED: {match.recommended}")
    print(f"REASON: {match.reason}")
    print(f"PULL: {match.pull_cmd}")

    if args.pull and not match.already_installed:
        print(f"pulling {match.recommended} …")
        code = pull_model(match.recommended)
        if code != 0:
            print(f"FAIL: ollama pull exit={code}", file=sys.stderr)
            return code
        print(f"PULLED OK: {match.recommended}")
    elif args.pull and match.already_installed:
        print(f"SKIP pull: already installed {match.recommended}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
