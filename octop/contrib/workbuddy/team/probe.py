# SPDX-License-Identifier: MIT
"""Probe local OpenAI-compatible LLM endpoints (Ollama first)."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class ProbeResult:
    ok: bool
    base_url: str
    models: list[str] = field(default_factory=list)
    error: str = ""
    preferred_model: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


CANDIDATE_BASES = (
    "http://127.0.0.1:11434/v1",  # Ollama
    "http://127.0.0.1:1234/v1",  # LM Studio
    "http://127.0.0.1:8080/v1",  # llama.cpp server
)


def _list_models(base_url: str, *, timeout_s: float = 5.0) -> list[str]:
    url = base_url.rstrip("/") + "/models"
    req = urllib.request.Request(url, method="GET", headers={"Authorization": "Bearer ollama"})
    with urllib.request.urlopen(req, timeout=timeout_s) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    data = payload.get("data") or payload.get("models") or []
    names: list[str] = []
    for item in data:
        if isinstance(item, dict):
            name = item.get("id") or item.get("name") or item.get("model")
            if name:
                names.append(str(name))
        elif isinstance(item, str):
            names.append(item)
    return names


def _prefer(models: list[str]) -> str:
    if not models:
        return ""
    # Prefer small/fast instruct-ish models for smoke
    ranked = (
        "qwen2.5:1.5b",
        "qwen2.5:3b",
        "qwen2.5:0.5b",
        "qwen2:1.5b",
        "llama3.2:1b",
        "llama3.2:3b",
        "phi3:mini",
        "tinyllama",
    )
    lower = {m.lower(): m for m in models}
    for key in ranked:
        if key in lower:
            return lower[key]
    for m in models:
        ml = m.lower()
        if any(x in ml for x in ("1.5b", "1b", "3b", "mini", "small", "qwen")):
            return m
    return models[0]


def probe_local_llm(
    bases: tuple[str, ...] | list[str] | None = None,
    *,
    timeout_s: float = 5.0,
) -> ProbeResult:
    """Return the first reachable local endpoint."""
    errors: list[str] = []
    for base in bases or CANDIDATE_BASES:
        try:
            models = _list_models(base, timeout_s=timeout_s)
            return ProbeResult(
                ok=True,
                base_url=base,
                models=models,
                preferred_model=_prefer(models),
            )
        except urllib.error.HTTPError as exc:
            errors.append(f"{base}: HTTP {exc.code}")
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{base}: {exc}")
    return ProbeResult(
        ok=False,
        base_url="",
        error="; ".join(errors) or "no candidate endpoints",
    )


def chat_smoke(
    *,
    base_url: str,
    model: str,
    timeout_s: float = 60.0,
) -> str:
    """One-shot chat completion to verify generation works."""
    url = base_url.rstrip("/") + "/chat/completions"
    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": "你是简洁助手，用一句话中文回答。"},
            {"role": "user", "content": "回复四个字：本地可用"},
        ],
        "temperature": 0.1,
        "max_tokens": 64,
        "stream": False,
    }
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        method="POST",
        headers={"Content-Type": "application/json", "Authorization": "Bearer ollama"},
    )
    with urllib.request.urlopen(req, timeout=timeout_s) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    return str(((payload.get("choices") or [{}])[0].get("message") or {}).get("content") or "")
