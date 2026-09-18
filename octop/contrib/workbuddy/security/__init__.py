# SPDX-License-Identifier: MIT
"""Permission / security policy store (ask | plan | craft | sandbox)."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

MODES = ("ask", "plan", "craft", "sandbox")


@dataclass
class SecurityPolicy:
    """Default tool / outbound / filesystem gates per execution mode."""

    default_mode: str = "craft"
    allow_outbound: bool = False
    allow_shell: bool = False
    allow_filesystem_write: bool = True
    require_confirm_destructive: bool = True
    sandbox_roots: list[str] = field(default_factory=list)
    denied_tools: list[str] = field(default_factory=list)
    allowed_tools: list[str] = field(default_factory=list)
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SecurityPolicy:
        mode = str(data.get("default_mode") or "craft")
        if mode not in MODES:
            mode = "craft"
        return cls(
            default_mode=mode,
            allow_outbound=bool(data.get("allow_outbound", False)),
            allow_shell=bool(data.get("allow_shell", False)),
            allow_filesystem_write=bool(data.get("allow_filesystem_write", True)),
            require_confirm_destructive=bool(data.get("require_confirm_destructive", True)),
            sandbox_roots=list(data.get("sandbox_roots") or []),
            denied_tools=list(data.get("denied_tools") or []),
            allowed_tools=list(data.get("allowed_tools") or []),
            notes=str(data.get("notes") or ""),
        )

    def allows_tool(self, tool_name: str) -> bool:
        name = tool_name.strip()
        if name in self.denied_tools:
            return False
        if self.allowed_tools and name not in self.allowed_tools:
            return False
        if name.startswith("shell") and not self.allow_shell:
            return False
        return True


class PolicyStore:
    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def load(self) -> SecurityPolicy:
        if not self.path.is_file():
            return SecurityPolicy()
        data = json.loads(self.path.read_text(encoding="utf-8"))
        return SecurityPolicy.from_dict(data if isinstance(data, dict) else {})

    def save(self, policy: SecurityPolicy) -> Path:
        self.path.write_text(
            json.dumps(policy.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return self.path

    def update(self, **fields: Any) -> SecurityPolicy:
        policy = self.load()
        data = policy.to_dict()
        data.update(fields)
        policy = SecurityPolicy.from_dict(data)
        self.save(policy)
        return policy
