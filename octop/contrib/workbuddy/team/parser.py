# SPDX-License-Identifier: MIT
"""Parse WorkBuddy team SOUL.md into structured TeamDefinition."""

from __future__ import annotations

import json
import re
from pathlib import Path

from .models import PhaseMode, TeamDefinition, TeamMember, TeamPhase

_AGENT_ID_RE = re.compile(r"`([a-z][a-z0-9-]{2,}?)(?:\.md)?`")
_PLAIN_ID_RE = re.compile(r"^[a-z][a-z0-9-]{2,}$")
_HEADING_MEMBER_RE = re.compile(
    r"^#{2,4}\s+(?:[^\s`]+\s+)?`([a-z][a-z0-9-]{2,}?)(?:\.md)?`"
    r"|^#{2,4}\s+(.+?)\s+`([a-z][a-z0-9-]{2,}?)(?:\.md)?`",
)
_NAME_SUBAGENT_RE = re.compile(
    r'name:\s*"([a-z][a-z0-9-]{2,})"\s*,\s*subagent_type:\s*"\1"',
)
_FRONTMATTER_NAME_RE = re.compile(
    r"^---\s*\n.*?^name:\s*(?P<name>[^\n]+)\n.*?^---",
    re.MULTILINE | re.DOTALL,
)
_PHASE_TOKEN_RE = re.compile(
    r"(Phase\s*\d+|阶段\s*\d+|圆桌|roundtable)",
    re.IGNORECASE,
)
_PARALLEL_RE = re.compile(r"并行|parallel", re.IGNORECASE)
_SEQUENTIAL_RE = re.compile(r"顺序|串行|sequential", re.IGNORECASE)

# Noise ids that appear in backticks but are not team members
_SKIP_IDS = frozenset(
    {
        "neodata-financial-search",
        "westock-data",
        "westock-tool",
        "md-to-html",
        "skills",
        "teamcreate",
        "team-create",
        "baseDir",
        "deliverables",
    }
)


def _strip_cell(text: str) -> str:
    return text.strip().strip("`").strip()


def _detect_mode(text: str) -> PhaseMode:
    if _SEQUENTIAL_RE.search(text):
        return "sequential"
    if _PARALLEL_RE.search(text):
        return "parallel"
    return "parallel"


def _detect_phase(text: str, default: str = "roundtable") -> str:
    m = _PHASE_TOKEN_RE.search(text)
    if not m:
        return default
    raw = m.group(1)
    digits = re.search(r"\d+", raw)
    if digits:
        return f"phase-{digits.group(0)}"
    if "圆桌" in raw or raw.lower() == "roundtable":
        return "roundtable"
    return default


def _extract_lead_id(soul: str, fallback: str) -> str:
    m = _FRONTMATTER_NAME_RE.search(soul)
    if m:
        return m.group("name").strip().strip('"').strip("'")
    # Prefer first YAML name: after second --- block (WorkBuddy often has two)
    names = re.findall(r"(?m)^name:\s*(.+)$", soul)
    if names:
        return names[-1].strip().strip('"').strip("'")
    return fallback


def _member_section_lines(soul: str) -> list[str]:
    """Lines under a roster section until the next H2."""
    section_titles = (
        "团队成员",
        "Team Members",
        "成员能力清单",
        "成员清单",
        "专家成员",
    )
    lines = soul.splitlines()
    in_member_section = False
    out: list[str] = []
    for line in lines:
        heading = line.strip().lstrip("#").strip()
        if line.startswith("## ") and any(t in heading for t in section_titles):
            in_member_section = True
            continue
        if in_member_section and line.startswith("## "):
            break
        if in_member_section:
            out.append(line)
    return out


def _find_member_table_rows(soul: str) -> list[str]:
    """Return markdown table body lines that look like member roster rows."""
    rows: list[str] = []
    section = _member_section_lines(soul)
    # If dedicated section empty, scan whole doc tables (last resort)
    scan_lines = section if section else soul.splitlines()
    for line in scan_lines:
        if "|" not in line:
            continue
        if re.match(r"^\s*\|?\s*[-:| ]+\s*\|?\s*$", line):
            continue
        lower = line.lower()
        if "agent id" in lower or "agent 名称" in lower or "agent名称" in lower:
            continue
        stripped = line.strip()
        cells = [_strip_cell(c) for c in stripped.strip("|").split("|")]
        if cells and cells[0] in {"成员", "标记", "角色", "Agent", "Agent ID", "Agent 名称"}:
            continue
        if _AGENT_ID_RE.search(line):
            rows.append(line)
            continue
        if any(
            _PLAIN_ID_RE.match(c) and c.lower() not in _SKIP_IDS
            for c in cells
        ):
            rows.append(line)
    return rows


def _parse_member_row(line: str, default_phase: str) -> TeamMember | None:
    cells = [_strip_cell(c) for c in line.strip().strip("|").split("|")]
    if len(cells) < 2:
        return None

    agent_ids = _AGENT_ID_RE.findall(line)
    agent_ids = [a for a in agent_ids if a.lower() not in _SKIP_IDS]
    agent_id = ""
    if agent_ids:
        agent_id = agent_ids[0]
    else:
        for c in cells:
            if _PLAIN_ID_RE.match(c) and c.lower() not in _SKIP_IDS:
                agent_id = c
                break
    if not agent_id:
        return None
    # Normalize filename-style ids
    if agent_id.endswith(".md"):
        agent_id = agent_id[: -len(".md")]

    # Locate which cell holds the agent id
    id_idx = 0
    for i, c in enumerate(cells):
        cleaned = c.replace("`", "").removesuffix(".md")
        if cleaned == agent_id or agent_id in cleaned:
            id_idx = i
            break

    emoji = ""
    display_name = agent_id
    alias = ""
    specialty = ""
    typical_query = ""
    phase_text = ""

    # Heuristics for the common WorkBuddy table shapes
    if id_idx == 0 and len(cells) >= 2:
        # | agent-id | 名字/头衔 | 职责... |  (ChatLaw / IndustrySre)
        display_name = cells[1] or agent_id
        specialty = cells[2] if len(cells) > 2 else ""
        if len(cells) > 3:
            specialty = " / ".join(c for c in cells[2:] if c)
    elif id_idx == 1 and len(cells) >= 5:
        # | emoji | `id` | alias | title | specialty |
        emoji = cells[0]
        alias = cells[2] if len(cells) > 2 else ""
        display_name = cells[3] if len(cells) > 3 else agent_id
        specialty = cells[4] if len(cells) > 4 else ""
    elif id_idx == 1 and len(cells) >= 4:
        # | title | `id` | specialty | typical | phase |
        # OR | title | `id.md` | specialty |
        display_name = cells[0] or agent_id
        specialty = cells[2] if len(cells) > 2 else ""
        typical_query = cells[3] if len(cells) > 3 else ""
        phase_text = cells[4] if len(cells) > 4 else ""
    else:
        # Best effort: first non-id cell as display name
        for c in cells:
            cleaned = c.replace("`", "").removesuffix(".md")
            if cleaned != agent_id and c and not c.startswith("Phase"):
                display_name = c
                break
        for c in cells:
            if "Phase" in c or "阶段" in c or "并行" in c or "顺序" in c:
                phase_text = c
            elif c and agent_id not in c.replace("`", "") and c != display_name:
                if not specialty:
                    specialty = c

    joined = " | ".join(cells)
    phase = _detect_phase(phase_text or joined, default=default_phase)
    mode = _detect_mode(phase_text or joined)

    return TeamMember(
        agent_id=agent_id,
        display_name=display_name,
        specialty=specialty,
        phase=phase,
        mode=mode,
        alias=alias,
        emoji=emoji,
        typical_query=typical_query,
    )


def _members_from_capability_bullets(soul: str) -> list[TeamMember]:
    """Parse ``- `agent-id`: specialty`` capability lists."""
    members: list[TeamMember] = []
    section = "\n".join(_member_section_lines(soul)) or soul
    for m in re.finditer(
        r"^[-*]\s+`([a-z][a-z0-9-]{2,}?)(?:\.md)?`\s*[:：]\s*(.+)$",
        section,
        re.MULTILINE,
    ):
        agent_id = m.group(1)
        if agent_id.lower() in _SKIP_IDS:
            continue
        specialty = m.group(2).strip()
        # Use first clause before period / semicolon as short display hint
        display = agent_id
        members.append(
            TeamMember(
                agent_id=agent_id,
                display_name=display,
                specialty=specialty[:200],
                phase="roundtable",
                mode="parallel",
            )
        )
    return members


def _members_from_headings(soul: str) -> list[TeamMember]:
    """Parse ``### Title `agent-id` `` style member cards (AShareAnalysis)."""
    members: list[TeamMember] = []
    section = "\n".join(_member_section_lines(soul)) or soul
    for line in section.splitlines():
        m = re.match(
            r"^#{2,4}\s+(?P<head>.+?)\s+`(?P<id>[a-z][a-z0-9-]{2,}?)(?:\.md)?`\s*$",
            line.strip(),
        )
        if not m:
            continue
        agent_id = m.group("id")
        if agent_id.lower() in _SKIP_IDS:
            continue
        head = m.group("head").strip()
        # Drop leading emoji / symbols
        display = re.sub(r"^[^\w\u4e00-\u9fff]+", "", head).strip() or agent_id
        members.append(
            TeamMember(
                agent_id=agent_id,
                display_name=display,
                specialty="",
                phase="roundtable",
                mode="parallel",
            )
        )
    return members


def _members_from_name_list(soul: str) -> list[TeamMember]:
    """Parse CRITICAL name/subagent_type bullet list."""
    members: list[TeamMember] = []
    for m in _NAME_SUBAGENT_RE.finditer(soul):
        agent_id = m.group(1)
        if agent_id.lower() in _SKIP_IDS:
            continue
        # Optional Chinese name after em-dash on same line
        display = agent_id
        line_start = soul.rfind("\n", 0, m.start()) + 1
        line_end = soul.find("\n", m.end())
        if line_end < 0:
            line_end = len(soul)
        line = soul[line_start:line_end]
        after = line[m.end() - line_start :]
        cn = re.search(r"[—–-]\s*(.+?)\s*$", after)
        if cn:
            display = cn.group(1).strip()
        members.append(
            TeamMember(
                agent_id=agent_id,
                display_name=display,
                specialty="",
                phase="roundtable",
                mode="parallel",
            )
        )
    return members


def _build_phases(members: list[TeamMember]) -> tuple[list[TeamPhase], str]:
    if not members:
        return [], "roundtable"

    phase_ids = []
    for m in members:
        if m.phase not in phase_ids:
            phase_ids.append(m.phase)

    # Single roundtable / unnamed phase → roundtable orchestration
    if len(phase_ids) == 1 and phase_ids[0] in ("roundtable", "default"):
        return (
            [
                TeamPhase(
                    id="roundtable",
                    name="圆桌并行",
                    mode="parallel",
                    member_ids=tuple(m.agent_id for m in members),
                )
            ],
            "roundtable",
        )

    phases: list[TeamPhase] = []
    for pid in phase_ids:
        bucket = [m for m in members if m.phase == pid]
        # Prefer sequential if any member marked sequential
        mode: PhaseMode = "sequential" if any(m.mode == "sequential" for m in bucket) else "parallel"
        # Human-readable name
        if pid.startswith("phase-"):
            name = f"Phase {pid.split('-', 1)[1]}"
            # annotate from first member mode hint
            if mode == "parallel":
                name += " 并行"
            else:
                name += " 顺序"
        else:
            name = pid
        phases.append(
            TeamPhase(
                id=pid,
                name=name,
                mode=mode,
                member_ids=tuple(m.agent_id for m in bucket),
            )
        )
    return phases, "phased"


def parse_team_soul(
    soul_text: str,
    *,
    expert_id: str = "",
    source: str = "",
) -> TeamDefinition:
    """Parse a team lead SOUL.md body into a TeamDefinition."""
    lead_id = _extract_lead_id(soul_text, fallback=f"{expert_id}-lead" if expert_id else "team-lead")
    # Lead display name: first H1/H2 after title
    lead_name = lead_id
    for line in soul_text.splitlines():
        if line.startswith("# ") and "主理人" in line:
            lead_name = line.lstrip("#").strip()
            break
        if line.startswith("## ") and ("·" in line or "主理人" in line):
            lead_name = line.lstrip("#").strip()
            break

    rows = _find_member_table_rows(soul_text)
    members: list[TeamMember] = []
    seen: set[str] = set()
    default_phase = "roundtable"

    def _add(member: TeamMember | None) -> None:
        if member is None or member.agent_id in seen:
            return
        if member.agent_id == lead_id:
            return
        seen.add(member.agent_id)
        members.append(member)

    for row in rows:
        _add(_parse_member_row(row, default_phase=default_phase))

    # Fallback 1: heading cards under roster section
    if not members:
        for m in _members_from_headings(soul_text):
            _add(m)

    # Fallback 2: capability bullet list (- `id`: ...)
    if not members:
        for m in _members_from_capability_bullets(soul_text):
            _add(m)

    # Fallback 3: name/subagent_type CRITICAL list
    if not members:
        for m in _members_from_name_list(soul_text):
            _add(m)

    phases, orchestration = _build_phases(members)
    return TeamDefinition(
        expert_id=expert_id,
        lead_id=lead_id,
        lead_name=lead_name,
        members=members,
        phases=phases,
        orchestration=orchestration,  # type: ignore[arg-type]
        source=source,
    )


def parse_team_expert_dir(expert_dir: Path) -> TeamDefinition:
    """Load SOUL.md (+ optional team.json) from an Octop expert directory."""
    expert_dir = Path(expert_dir)
    team_json = expert_dir / "team.json"
    if team_json.is_file():
        data = json.loads(team_json.read_text(encoding="utf-8"))
        return TeamDefinition.from_dict(data)

    soul_path = expert_dir / "SOUL.md"
    if not soul_path.is_file():
        raise FileNotFoundError(f"SOUL.md not found in {expert_dir}")
    soul = soul_path.read_text(encoding="utf-8")
    return parse_team_soul(
        soul,
        expert_id=expert_dir.name,
        source=str(soul_path),
    )


def member_system_prompt(member: TeamMember, team: TeamDefinition) -> str:
    """Synthesize a member subagent system prompt from roster metadata."""
    parts = [
        f"---",
        f"name: {member.agent_id}",
        f"description: {member.display_name} — {member.specialty or 'team specialist'}",
        f"---",
        "",
        f"# {member.display_name}",
    ]
    if member.alias:
        parts.append(f"**花名**：{member.alias}")
    if member.emoji:
        parts.append(f"**标记**：{member.emoji}")
    parts.extend(
        [
            "",
            f"你是「{team.lead_name}」所调度的团队成员 **{member.display_name}**"
            f"（Agent ID: `{member.agent_id}`）。",
            "",
            "## 职责边界",
            member.specialty or "按主理人下发的研究维度独立产出专业意见。",
            "",
            "## 协作铁律",
            "- 只对本职责维度发声，不代写其他成员结论",
            "- 产出回传主理人；禁止与其他成员直连",
            "- 基于任务说明中的用户问题独立分析",
            "",
        ]
    )
    if member.typical_query:
        parts.extend(["## 典型问法", member.typical_query, ""])
    return "\n".join(parts).rstrip() + "\n"


def write_team_artifacts(expert_dir: Path, definition: TeamDefinition | None = None) -> TeamDefinition:
    """Write ``team.json`` and ``agents/<id>.md`` under *expert_dir*."""
    import os
    import stat
    import time

    expert_dir = Path(expert_dir)
    if definition is None:
        definition = parse_team_expert_dir(expert_dir)

    def _safe_write(path: Path, text: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        last_err: Exception | None = None
        for _ in range(5):
            try:
                if path.exists():
                    try:
                        os.chmod(path, stat.S_IWRITE | stat.S_IREAD)
                    except OSError:
                        pass
                path.write_text(text, encoding="utf-8")
                return
            except PermissionError as exc:
                last_err = exc
                time.sleep(0.15)
        if last_err is not None:
            raise last_err

    _safe_write(
        expert_dir / "team.json",
        json.dumps(definition.to_dict(), ensure_ascii=False, indent=2) + "\n",
    )

    agents_dir = expert_dir / "agents"
    agents_dir.mkdir(parents=True, exist_ok=True)
    for member in definition.members:
        path = agents_dir / f"{member.agent_id}.md"
        try:
            _safe_write(path, member_system_prompt(member, definition))
        except PermissionError:
            # Roster JSON is enough for runtime; member md is best-effort seed.
            continue

    return definition
