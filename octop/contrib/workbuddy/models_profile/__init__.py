# SPDX-License-Identifier: MIT
"""Model profile store — local OpenAI-compatible endpoints."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class ModelProfile:
    profile_id: str
    base_url: str
    model: str
    api_key_env: str = "OPENAI_API_KEY"
    temperature: float = 0.2
    max_tokens: int = 4096
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ModelProfile:
        return cls(
            profile_id=str(data["profile_id"]),
            base_url=str(data.get("base_url") or "http://127.0.0.1:8000/v1"),
            model=str(data.get("model") or "default"),
            api_key_env=str(data.get("api_key_env") or "OPENAI_API_KEY"),
            temperature=float(data.get("temperature", 0.2)),
            max_tokens=int(data.get("max_tokens", 4096)),
            extra=dict(data.get("extra") or {}),
        )


class ModelProfileStore:
    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _load_all(self) -> dict[str, Any]:
        if not self.path.is_file():
            return {"active": "", "profiles": {}}
        data = json.loads(self.path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return {"active": "", "profiles": {}}
        data.setdefault("active", "")
        data.setdefault("profiles", {})
        return data

    def _save_all(self, data: dict[str, Any]) -> None:
        self.path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def list(self) -> list[ModelProfile]:
        data = self._load_all()
        out: list[ModelProfile] = []
        for pid, row in (data.get("profiles") or {}).items():
            if isinstance(row, dict):
                row = {**row, "profile_id": pid}
                out.append(ModelProfile.from_dict(row))
        return out

    def get(self, profile_id: str) -> ModelProfile:
        data = self._load_all()
        row = (data.get("profiles") or {}).get(profile_id)
        if not isinstance(row, dict):
            raise FileNotFoundError(f"profile not found: {profile_id}")
        return ModelProfile.from_dict({**row, "profile_id": profile_id})

    def upsert(self, profile: ModelProfile) -> ModelProfile:
        data = self._load_all()
        profiles = data.setdefault("profiles", {})
        profiles[profile.profile_id] = profile.to_dict()
        if not data.get("active"):
            data["active"] = profile.profile_id
        self._save_all(data)
        return profile

    def set_active(self, profile_id: str) -> ModelProfile:
        profile = self.get(profile_id)
        data = self._load_all()
        data["active"] = profile_id
        self._save_all(data)
        return profile

    def active(self) -> ModelProfile | None:
        data = self._load_all()
        aid = str(data.get("active") or "")
        if not aid:
            return None
        try:
            return self.get(aid)
        except FileNotFoundError:
            return None
