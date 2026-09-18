# SPDX-License-Identifier: MIT
"""Ask / Plan / Craft work modes — WorkBuddy parity (stdlib assembler).

Default path: layered identity + expert + memory + mode gate.
Optional ``use_official_tpl=True`` renders vendor Nunjucks ``.tpl`` via
``templates.nunjucks_lite``.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

WorkMode = Literal["ask", "plan", "craft"]

_OFFICIAL_TPL = {
    "ask": "workbuddy-ask-prompt.tpl",
    "plan": "workbuddy-prompt.tpl",
    "craft": "workbuddy-prompt.tpl",
}

_MODE_REMINDERS: dict[WorkMode, str] = {
    "ask": (
        "<ask_mode>\n"
        "Ask mode is active. Answer questions only. Do NOT edit files, run "
        "mutating shell commands, change configs, or commit. If the user asks "
        "for changes, remind them to switch to Craft mode.\n"
        "</ask_mode>"
    ),
    "plan": (
        "<plan_mode>\n"
        "Plan mode is active. Produce a clear, ordered plan with acceptance "
        "checks. Prefer read-only investigation. Do not apply irreversible "
        "changes until the user switches to Craft / Goal run.\n"
        "</plan_mode>"
    ),
    "craft": (
        "<craft_mode>\n"
        "Craft mode is active. You may create and edit files to complete the "
        "task. Prefer small, verifiable steps and report what you changed.\n"
        "</craft_mode>"
    ),
}


@dataclass
class AssembledPrompt:
    mode: WorkMode
    system: str
    sections: list[str]

    def to_dict(self) -> dict:
        return {"mode": self.mode, "system": self.system, "sections": list(self.sections)}


def normalize_mode(raw: str | None) -> WorkMode:
    m = (raw or "craft").strip().lower()
    if m in {"ask", "plan", "craft"}:
        return m  # type: ignore[return-value]
    aliases = {"readonly": "ask", "read": "ask", "planning": "plan", "write": "craft", "edit": "craft"}
    return aliases.get(m, "craft")  # type: ignore[return-value]


def assemble_system_prompt(
    *,
    mode: WorkMode | str = "craft",
    expert_prompt: str = "",
    expert_id: str = "",
    soul: str = "",
    user_profile: str = "",
    working_memory: str = "",
    durable_memory: str = "",
    model_name: str = "local",
    extra: str = "",
    use_official_tpl: bool = False,
    templates_root: Path | str | None = None,
) -> AssembledPrompt:
    """Build a system prompt with WorkBuddy-like layering."""
    mode_n = normalize_mode(mode if isinstance(mode, str) else mode)

    if use_official_tpl:
        from ..templates.nunjucks_lite import default_templates_root, render_file

        root = Path(templates_root) if templates_root else default_templates_root()
        tpl_name = _OFFICIAL_TPL.get(mode_n, "workbuddy-prompt.tpl")
        tpl_path = root / tpl_name
        if tpl_path.is_file():
            ctx = {
                "modelName": model_name or "local",
                "SoulContent": soul,
                "UserContent": user_profile,
                "WorkingMemoryContent": working_memory,
                "UserMemoryContent": durable_memory,
                "SoulPath": "SOUL.md",
                "UserPath": "USER.md",
                "IdentityPath": "IDENTITY.md",
                "BootstrapPath": "BOOTSTRAP.md",
                "BootstrapContent": "",
                "IdentityContent": "",
                "WorkspaceIdentityMode": "active" if (soul.strip() or user_profile.strip()) else "",
                "dataFolderName": ".workbuddy",
                "ClawMemory_1": expert_prompt,
            }
            rendered = render_file(tpl_path, ctx)
            if extra.strip():
                rendered = rendered.rstrip() + "\n\n" + extra.strip()
            if mode_n == "plan" and "<plan_mode>" not in rendered:
                rendered = rendered.rstrip() + "\n\n" + _MODE_REMINDERS["plan"]
            return AssembledPrompt(mode=mode_n, system=rendered, sections=["official_tpl", tpl_name])

    sections: list[str] = []

    sections.append(f"this conversation is powered by {model_name or 'local'}")

    if soul.strip() or user_profile.strip():
        block = ["<identity_context>"]
        if soul.strip():
            block.append("## SOUL.md\n" + soul.strip())
        if user_profile.strip():
            block.append("## USER.md\n" + user_profile.strip())
        block.append("</identity_context>")
        sections.append("\n\n".join(block))

    if expert_prompt.strip():
        header = (
            "**Role Override:** The following expert role definition takes precedence "
            "over any previously established persona. "
        )
        if expert_id:
            header += f"(expert_id=`{expert_id}`) "
        sections.append(header + "\n\n" + expert_prompt.strip())

    if working_memory.strip():
        sections.append("## Working memory\n" + working_memory.strip())
    if durable_memory.strip():
        sections.append("## Durable memory (MEMORY.md)\n" + durable_memory.strip())

    if extra.strip():
        sections.append(extra.strip())

    sections.append(_MODE_REMINDERS[mode_n])

    system = "\n\n".join(s for s in sections if s.strip())
    return AssembledPrompt(mode=mode_n, system=system, sections=sections)


def mode_allows_writes(mode: WorkMode | str) -> bool:
    return normalize_mode(mode) == "craft"


def mode_allows_mutating_tools(mode: WorkMode | str) -> bool:
    return normalize_mode(mode) == "craft"
