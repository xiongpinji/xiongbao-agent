# SPDX-License-Identifier: MIT
"""Build a 50-task smoke sample from the converted expert library.

Sampling policy (deterministic, seed-stable):
- All 33 team experts (welcome_message.zh as prompt)
- 17 agent experts evenly spaced across the agent list

When the official Office subset is on disk, ``list_office_tasks`` can
surface those 50 Harbor tasks for the upstream runner.
"""

from __future__ import annotations

import json
from pathlib import Path

from .models import BenchTask

_DEFAULT_SMOKE_N = 50
_TEAM_SLOTS = 33
_AGENT_SLOTS = 17


def default_library_root(project_root: Path | None = None) -> Path:
    # Path: <project>/octop/contrib/workbuddy/bench/sample.py
    # parents[0]=bench … [3]=octop/ … library lives under octop/src/...
    octop_dir = Path(__file__).resolve().parents[3]
    if project_root is not None:
        octop_dir = Path(project_root) / "octop"
    return (
        octop_dir
        / "src"
        / "octop"
        / "infra"
        / "agents"
        / "experts"
        / "library"
    )


def _zh_text(obj: object) -> str:
    if isinstance(obj, dict):
        return str(obj.get("zh") or obj.get("en") or "").strip()
    if isinstance(obj, str):
        return obj.strip()
    return ""


def _load_manifest(expert_dir: Path) -> dict:
    path = expert_dir / "manifest.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _iter_wb_experts(library: Path) -> list[tuple[Path, dict, str]]:
    out: list[tuple[Path, dict, str]] = []
    for d in sorted(library.iterdir()):
        if not d.is_dir():
            continue
        mj = d / "manifest.json"
        if not mj.is_file():
            continue
        try:
            m = _load_manifest(d)
        except (OSError, json.JSONDecodeError):
            continue
        wb = m.get("_wb") or {}
        if not wb:
            continue
        kind = str(wb.get("expert_type") or "")
        if kind in {"agent", "team", "plugin"}:
            out.append((d, m, kind))
    return out


def build_smoke_sample(
    library: Path | None = None,
    *,
    n: int = _DEFAULT_SMOKE_N,
) -> list[BenchTask]:
    """Return up to ``n`` smoke tasks (default 50 = 33 teams + 17 agents)."""
    library = Path(library) if library else default_library_root()
    if not library.is_dir():
        raise FileNotFoundError(f"expert library not found: {library}")

    experts = _iter_wb_experts(library)
    teams = [(d, m) for d, m, k in experts if k == "team"]
    agents = [(d, m) for d, m, k in experts if k == "agent"]

    tasks: list[BenchTask] = []

    for d, m in teams[:_TEAM_SLOTS]:
        prompt = _zh_text(m.get("welcome_message")) or f"请以 {d.name} 专家团完成一次典型协作任务"
        cat = ((m.get("_wb") or {}).get("category_label") or {})
        tasks.append(
            BenchTask(
                task_id=f"smoke-team-{d.name}",
                kind="team",
                expert_id=d.name,
                prompt=prompt,
                category=_zh_text(cat) or str((m.get("_wb") or {}).get("category_id") or ""),
                source="smoke",
                meta={"expert_dir": str(d)},
            )
        )

    # Evenly spaced agents for diversity
    agent_slots = min(_AGENT_SLOTS, max(0, n - len(tasks)), len(agents))
    if agent_slots and agents:
        step = max(1, len(agents) // agent_slots)
        picked: list[tuple[Path, dict]] = []
        for i in range(agent_slots):
            idx = min(i * step, len(agents) - 1)
            picked.append(agents[idx])
        # Deduplicate if step collapses
        seen: set[str] = set()
        unique: list[tuple[Path, dict]] = []
        for item in picked:
            if item[0].name in seen:
                continue
            seen.add(item[0].name)
            unique.append(item)
        # Fill remaining from unused agents
        for d, m in agents:
            if len(unique) >= agent_slots:
                break
            if d.name not in seen:
                seen.add(d.name)
                unique.append((d, m))
        for d, m in unique[:agent_slots]:
            prompt = _zh_text(m.get("welcome_message")) or f"请以 {d.name} 专家完成一次典型咨询"
            cat = ((m.get("_wb") or {}).get("category_label") or {})
            tasks.append(
                BenchTask(
                    task_id=f"smoke-agent-{d.name}",
                    kind="agent",
                    expert_id=d.name,
                    prompt=prompt,
                    category=_zh_text(cat) or str((m.get("_wb") or {}).get("category_id") or ""),
                    source="smoke",
                    meta={"expert_dir": str(d)},
                )
            )

    return tasks[:n]


def default_office_dataset_root(project_root: Path | None = None) -> Path:
    root = project_root or Path(__file__).resolve().parents[4]
    return root / "vendor" / "workbuddy-bench" / "datasets" / "wb-bench-office-v1.0"


def list_office_tasks(dataset_root: Path | None = None) -> list[BenchTask]:
    """List official Office subset tasks if the archive was extracted."""
    root = Path(dataset_root) if dataset_root else default_office_dataset_root()
    tasks_dir = root / "tasks"
    if not tasks_dir.is_dir():
        return []

    out: list[BenchTask] = []
    for d in sorted(tasks_dir.iterdir()):
        if not d.is_dir():
            continue
        instruction = d / "instruction.md"
        prompt = ""
        if instruction.is_file():
            prompt = instruction.read_text(encoding="utf-8", errors="replace").strip()
        out.append(
            BenchTask(
                task_id=f"office-{d.name}",
                kind="office",
                expert_id=d.name,
                prompt=prompt or f"(office task {d.name})",
                category="office",
                source="workbuddy-bench-office",
                meta={"task_dir": str(d)},
            )
        )
    return out


def write_sample_json(tasks: list[BenchTask], path: Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": 1,
        "suite": "workbuddy-smoke-50",
        "count": len(tasks),
        "tasks": [t.to_dict() for t in tasks],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
