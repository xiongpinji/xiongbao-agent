# SPDX-License-Identifier: MIT
"""OpenAI-compatible local LLM caller (Ollama / LM Studio / llama.cpp).

Uses only the stdlib so it runs under ``python -S``. Talks to
``POST {base_url}/chat/completions``.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any


DEFAULT_BASE_URL = "http://127.0.0.1:11434/v1"
DEFAULT_MODEL = "qwen2.5:1.5b"
# Small local models choke on full SOUL.md — keep a hard cap.
DEFAULT_SYSTEM_CHARS = 6000
DEFAULT_TIMEOUT_S = 180.0


@dataclass
class LLMCallStats:
    """Lightweight counters for one caller instance."""

    calls: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    errors: int = 0


class OpenAICompatCaller:
    """MemberCaller backed by an OpenAI-compatible chat API."""

    def __init__(
        self,
        *,
        base_url: str | None = None,
        model: str | None = None,
        api_key: str | None = None,
        temperature: float = 0.3,
        max_tokens: int = 1024,
        system_chars: int = DEFAULT_SYSTEM_CHARS,
        timeout_s: float = DEFAULT_TIMEOUT_S,
    ) -> None:
        self.base_url = (base_url or os.environ.get("WB_LLM_BASE_URL") or DEFAULT_BASE_URL).rstrip(
            "/"
        )
        self.model = model or os.environ.get("WB_LLM_MODEL") or DEFAULT_MODEL
        self.api_key = api_key or os.environ.get("WB_LLM_API_KEY") or "ollama"
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.system_chars = system_chars
        self.timeout_s = timeout_s
        self.stats = LLMCallStats()

    def _truncate(self, text: str, limit: int) -> str:
        if len(text) <= limit:
            return text
        return text[: limit - 80] + "\n\n…[system prompt truncated for local model]…"

    def _post_chat(self, messages: list[dict[str, str]]) -> str:
        url = f"{self.base_url}/chat/completions"
        body = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "stream": False,
        }
        data = json.dumps(body).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            method="POST",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
        )
        self.stats.calls += 1
        try:
            with urllib.request.urlopen(req, timeout=self.timeout_s) as resp:
                raw = resp.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            self.stats.errors += 1
            detail = exc.read().decode("utf-8", errors="replace")[:500]
            raise RuntimeError(f"LLM HTTP {exc.code} at {url}: {detail}") from exc
        except urllib.error.URLError as exc:
            self.stats.errors += 1
            raise RuntimeError(f"LLM unreachable at {url}: {exc.reason}") from exc

        payload = json.loads(raw)
        usage = payload.get("usage") or {}
        self.stats.prompt_tokens += int(usage.get("prompt_tokens") or 0)
        self.stats.completion_tokens += int(usage.get("completion_tokens") or 0)
        choices = payload.get("choices") or []
        if not choices:
            raise RuntimeError(f"LLM returned no choices: {raw[:300]}")
        message = choices[0].get("message") or {}
        content = message.get("content")
        if not isinstance(content, str) or not content.strip():
            raise RuntimeError(f"LLM empty content: {raw[:300]}")
        return content.strip()

    async def __call__(
        self,
        *,
        role: str,
        agent_id: str,
        display_name: str,
        system_prompt: str,
        user_message: str,
        context: dict[str, Any],
    ) -> str:
        # asyncio-friendly: blocking HTTP is fine for local smoke; wrap via to_thread if needed
        import asyncio

        system = self._truncate(system_prompt, self.system_chars)
        # Lead SOUL is huge — prefer a shorter synthesis brief
        if role == "lead" and len(system_prompt) > self.system_chars:
            system = (
                f"你是专家团主理人「{display_name}」(`{agent_id}`)。"
                "根据各成员回传，输出结构化中文综合报告："
                "结论摘要 / 各方要点 / 分歧与风险 / 可执行建议。"
            )
        prefix = f"[role={role} agent={agent_id} name={display_name}]"
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": f"{prefix}\n\n{user_message}"},
        ]
        return await asyncio.to_thread(self._post_chat, messages)

    def complete(self, *, system: str, user: str) -> str:
        """Synchronous chat completion (Teach drafter / scripts)."""
        system = self._truncate(system, self.system_chars)
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]
        return self._post_chat(messages)


# Back-compat alias
LocalLLMCaller = OpenAICompatCaller
