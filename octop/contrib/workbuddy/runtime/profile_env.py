# SPDX-License-Identifier: MIT
"""Apply active ModelProfile into process env for LLM callers."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from ..models_profile import ModelProfile, ModelProfileStore


def resolve_active_profile(
    path: Path | str | None = None,
) -> ModelProfile | None:
    store = ModelProfileStore(path or Path("artifacts/models/profiles.json"))
    try:
        return store.active()
    except Exception:
        return None


def apply_profile_env(
    profile: ModelProfile | None = None,
    *,
    path: Path | str | None = None,
    environ: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Set WB_LLM_* / OPENAI_* style vars from profile. Returns applied map."""
    env = environ if environ is not None else os.environ  # type: ignore[assignment]
    prof = profile if profile is not None else resolve_active_profile(path)
    if prof is None:
        return {"applied": False, "reason": "no active profile"}
    mapping = {
        "WB_LLM_BASE_URL": prof.base_url,
        "WB_LLM_MODEL": prof.model,
        "OPENAI_BASE_URL": prof.base_url,
        "OPENAI_MODEL": prof.model,
        "WB_MODEL_PROFILE": prof.profile_id,
    }
    for key, val in mapping.items():
        env[key] = val
    if prof.api_key_env and prof.api_key_env not in env:
        # leave key unset; callers read from named env
        pass
    return {
        "applied": True,
        "profile_id": prof.profile_id,
        "base_url": prof.base_url,
        "model": prof.model,
        "keys": list(mapping.keys()),
    }
