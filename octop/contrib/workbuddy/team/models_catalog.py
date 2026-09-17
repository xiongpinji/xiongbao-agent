# SPDX-License-Identifier: MIT
"""Match WorkBuddy team needs to downloadable Ollama models.

Profiles (requirement → model):

| profile     | use case                         | default pull      | ~size |
|-------------|----------------------------------|-------------------|-------|
| smoke       | CI / 2-member live gate          | qwen2.5:1.5b      | ~1 GB |
| team        | CN team (2–4 members)            | qwen2.5:3b        | ~2 GB |
| team-full   | 6-member StockPartner-class      | qwen2.5:7b        | ~4.7GB|
| strong      | better synthesis / long SOUL     | qwen2.5:14b       | ~9 GB |

Matching also considers free disk and optional VRAM hints.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal


ProfileId = Literal["smoke", "team", "team-full", "strong"]


@dataclass(frozen=True)
class ModelSpec:
    name: str
    profile: ProfileId
    approx_gb: float
    min_vram_gb: float
    langs: tuple[str, ...]
    notes: str = ""


CATALOG: tuple[ModelSpec, ...] = (
    ModelSpec(
        name="qwen2.5:1.5b",
        profile="smoke",
        approx_gb=1.0,
        min_vram_gb=1.5,
        langs=("zh", "en"),
        notes="最快冒烟；完整 6 人组质量不足",
    ),
    ModelSpec(
        name="qwen2.5:3b",
        profile="team",
        approx_gb=2.0,
        min_vram_gb=2.5,
        langs=("zh", "en"),
        notes="中文 Team 推荐默认（2–4 成员）",
    ),
    ModelSpec(
        name="qwen2.5:7b",
        profile="team-full",
        approx_gb=4.7,
        min_vram_gb=4.0,
        langs=("zh", "en"),
        notes="6 人专家团 + 主理人综合",
    ),
    ModelSpec(
        name="qwen2.5:14b",
        profile="strong",
        approx_gb=9.0,
        min_vram_gb=8.0,
        langs=("zh", "en"),
        notes="长 SOUL / 更高质量综合；显存不足会落到 CPU",
    ),
    # Fallbacks / alternates
    ModelSpec(
        name="llama3.2:3b",
        profile="team",
        approx_gb=2.0,
        min_vram_gb=2.5,
        langs=("en",),
        notes="英文备选",
    ),
)


@dataclass
class HostHints:
    free_disk_gb: float
    vram_gb: float | None = None
    installed: list[str] = field(default_factory=list)


@dataclass
class MatchResult:
    profile: ProfileId
    recommended: str
    alternatives: list[str]
    already_installed: bool
    pull_cmd: str
    reason: str
    skipped: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def default_models_for_profile(profile: ProfileId) -> list[ModelSpec]:
    primary = [m for m in CATALOG if m.profile == profile]
    # Prefer zh-capable Qwen first within profile
    primary.sort(key=lambda m: (0 if "zh" in m.langs else 1, m.approx_gb))
    return primary


def detect_host(*, ollama_models: list[str] | None = None) -> HostHints:
    disk = shutil.disk_usage(Path.home())
    free_gb = disk.free / (1024**3)
    vram: float | None = None
    env_vram = os.environ.get("WB_LLM_VRAM_GB")
    if env_vram:
        try:
            vram = float(env_vram)
        except ValueError:
            vram = None
    return HostHints(
        free_disk_gb=free_gb,
        vram_gb=vram,
        installed=list(ollama_models or []),
    )


_PROFILE_RANK: dict[str, int] = {
    "smoke": 0,
    "team": 1,
    "team-full": 2,
    "strong": 3,
}


def match_model(
    profile: ProfileId = "team",
    *,
    host: HostHints | None = None,
    prefer_installed: bool = True,
) -> MatchResult:
    """Pick the best downloadable model for *profile* given host constraints."""
    host = host or detect_host()
    need_rank = _PROFILE_RANK[profile]
    candidates = default_models_for_profile(profile)
    # Also allow stepping down within catalog if profile primary too heavy
    if profile == "team-full":
        candidates = candidates + default_models_for_profile("team") + default_models_for_profile(
            "smoke"
        )
    elif profile == "strong":
        candidates = (
            candidates
            + default_models_for_profile("team-full")
            + default_models_for_profile("team")
        )
    elif profile == "team":
        candidates = candidates + default_models_for_profile("smoke")

    skipped: list[str] = []
    fitted: list[ModelSpec] = []
    for spec in candidates:
        # Need ~1.2x model size free on disk
        if host.free_disk_gb < spec.approx_gb * 1.2:
            skipped.append(
                f"{spec.name}: disk {host.free_disk_gb:.1f}GB < need ~{spec.approx_gb * 1.2:.1f}GB"
            )
            continue
        if host.vram_gb is not None and host.vram_gb + 0.5 < spec.min_vram_gb:
            if spec.min_vram_gb > host.vram_gb * 1.8:
                skipped.append(
                    f"{spec.name}: vram hint {host.vram_gb:.1f}GB << {spec.min_vram_gb:.1f}GB"
                )
                continue
        fitted.append(spec)

    if not fitted:
        for spec in sorted(CATALOG, key=lambda m: m.approx_gb):
            if host.free_disk_gb >= spec.approx_gb * 1.2:
                fitted.append(spec)
                break

    if not fitted:
        return MatchResult(
            profile=profile,
            recommended="",
            alternatives=[],
            already_installed=False,
            pull_cmd="",
            reason="no model fits free disk",
            skipped=skipped,
        )

    # Prefer exact profile match among fitted, then closest higher/lower by rank
    def sort_key(m: ModelSpec) -> tuple[int, int | float, float]:
        rank = _PROFILE_RANK.get(m.profile, 0)
        # Exact profile first; then nearest without going far above VRAM
        return (abs(rank - need_rank), -rank if rank <= need_rank else rank, m.approx_gb)

    fitted_sorted = sorted(fitted, key=lambda m: (0 if m.profile == profile else 1, *sort_key(m)))

    installed_set = {n.lower() for n in host.installed}
    if prefer_installed:
        for spec in fitted_sorted:
            if spec.name.lower() not in installed_set:
                continue
            # Only reuse installed if it meets required profile tier
            if _PROFILE_RANK.get(spec.profile, 0) >= need_rank:
                return MatchResult(
                    profile=profile,
                    recommended=spec.name,
                    alternatives=[m.name for m in fitted_sorted if m.name != spec.name][:3],
                    already_installed=True,
                    pull_cmd=f"ollama pull {spec.name}",
                    reason=f"already installed and meets profile={profile}",
                    skipped=skipped,
                )

    best = fitted_sorted[0]
    return MatchResult(
        profile=profile,
        recommended=best.name,
        alternatives=[m.name for m in fitted_sorted if m.name != best.name][:3],
        already_installed=best.name.lower() in installed_set,
        pull_cmd=f"ollama pull {best.name}",
        reason=(
            f"matched profile={profile} size≈{best.approx_gb}GB "
            f"disk_free={host.free_disk_gb:.1f}GB"
            + (f" vram_hint={host.vram_gb}GB" if host.vram_gb is not None else "")
        ),
        skipped=skipped,
    )


def pull_model(
    name: str,
    *,
    ollama_exe: str | None = None,
    env: dict[str, str] | None = None,
) -> int:
    """Run ``ollama pull <name>``. Returns process exit code."""
    exe = ollama_exe or os.environ.get("OLLAMA_EXE") or _find_ollama()
    if not exe:
        raise FileNotFoundError("ollama executable not found")
    run_env = os.environ.copy()
    if env:
        run_env.update(env)
    # Prefer user models dir to avoid broken C:\\ollama_models junctions
    run_env.setdefault(
        "OLLAMA_MODELS",
        str(Path.home() / ".ollama" / "models"),
    )
    proc = subprocess.run(
        [exe, "pull", name],
        env=run_env,
        check=False,
    )
    return int(proc.returncode)


def _find_ollama() -> str | None:
    which = shutil.which("ollama")
    if which:
        return which
    win = Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Ollama" / "ollama.exe"
    if win.is_file():
        return str(win)
    return None


def catalog_json() -> str:
    return json.dumps(
        {
            "schema_version": 1,
            "profiles": {
                "smoke": "CI / 2-member live gate",
                "team": "CN team 2–4 members (default)",
                "team-full": "6-member expert team",
                "strong": "higher quality synthesis",
            },
            "models": [asdict(m) for m in CATALOG],
        },
        ensure_ascii=False,
        indent=2,
    )
