# SPDX-License-Identifier: MIT
"""Policy gate before Task / Goal execution."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..security import PolicyStore, SecurityPolicy


@dataclass
class PolicyDecision:
    allowed: bool
    mode: str
    reason: str = ""
    policy: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "allowed": self.allowed,
            "mode": self.mode,
            "reason": self.reason,
            "policy": self.policy or {},
        }


def load_policy(path: Path | str | None = None) -> SecurityPolicy:
    p = Path(path) if path else Path("artifacts/security/policy.json")
    return PolicyStore(p).load()


def check_run_allowed(
    *,
    mode: str,
    policy: SecurityPolicy | None = None,
    policy_path: Path | str | None = None,
    needs_write: bool = True,
    needs_shell: bool = False,
    needs_outbound: bool = False,
    tool_name: str = "",
) -> PolicyDecision:
    """Return whether a run may proceed under the active security policy.

    - ``ask`` / ``plan`` refuse filesystem writes and shell by default.
    - ``craft`` / ``sandbox`` follow policy flags.
    """
    pol = policy or load_policy(policy_path)
    m = (mode or pol.default_mode or "craft").strip().lower()
    if m not in {"ask", "plan", "craft", "sandbox"}:
        m = pol.default_mode

    if tool_name and not pol.allows_tool(tool_name):
        return PolicyDecision(
            False, m, f"tool denied: {tool_name}", pol.to_dict()
        )

    if needs_shell and not pol.allow_shell:
        return PolicyDecision(False, m, "shell not allowed by policy", pol.to_dict())

    if needs_outbound and not pol.allow_outbound:
        return PolicyDecision(False, m, "outbound not allowed by policy", pol.to_dict())

    if needs_write and m in {"ask", "plan"}:
        return PolicyDecision(
            False,
            m,
            f"mode={m} forbids writes — switch to craft/sandbox",
            pol.to_dict(),
        )

    if needs_write and not pol.allow_filesystem_write:
        return PolicyDecision(False, m, "filesystem write disabled", pol.to_dict())

    return PolicyDecision(True, m, "ok", pol.to_dict())
