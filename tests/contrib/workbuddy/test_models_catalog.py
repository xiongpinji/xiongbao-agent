# SPDX-License-Identifier: MIT
"""Unit tests for requirement → Ollama model matching."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT))

from octop.contrib.workbuddy.team.models_catalog import HostHints, match_model  # noqa: E402


def test_team_prefers_3b_over_installed_smoke() -> None:
    host = HostHints(
        free_disk_gb=50.0,
        vram_gb=4.0,
        installed=["qwen2.5:1.5b"],
    )
    result = match_model("team", host=host, prefer_installed=True)
    assert result.recommended == "qwen2.5:3b"
    assert result.already_installed is False


def test_team_reuses_installed_3b() -> None:
    host = HostHints(
        free_disk_gb=50.0,
        vram_gb=4.0,
        installed=["qwen2.5:1.5b", "qwen2.5:3b"],
    )
    result = match_model("team", host=host, prefer_installed=True)
    assert result.recommended == "qwen2.5:3b"
    assert result.already_installed is True


def test_team_full_prefers_7b() -> None:
    host = HostHints(free_disk_gb=80.0, vram_gb=4.0, installed=[])
    result = match_model("team-full", host=host)
    assert result.recommended == "qwen2.5:7b"


def test_smoke_uses_1_5b() -> None:
    host = HostHints(free_disk_gb=20.0, vram_gb=4.0, installed=[])
    result = match_model("smoke", host=host)
    assert result.recommended == "qwen2.5:1.5b"


def test_disk_too_small_skips_heavy() -> None:
    host = HostHints(free_disk_gb=1.5, vram_gb=4.0, installed=[])
    result = match_model("team-full", host=host)
    # 7b needs ~5.6GB free; should step down to team/smoke
    assert result.recommended in {"qwen2.5:1.5b", "qwen2.5:3b", ""}


if __name__ == "__main__":
    test_team_prefers_3b_over_installed_smoke()
    test_team_reuses_installed_3b()
    test_team_full_prefers_7b()
    test_smoke_uses_1_5b()
    test_disk_too_small_skips_heavy()
    print("ALL MATCH TESTS OK")
