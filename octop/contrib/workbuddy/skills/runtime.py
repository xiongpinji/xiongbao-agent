# SPDX-License-Identifier: MIT
"""Skill runtime — enable set, prompt pack, optional LLM invoke."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from .catalog import SkillCatalog
from .models import SkillPackage
from .sandbox import ScriptRunResult, list_skill_scripts, run_skill_script


def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class SkillRuntime:
    """Bind SkillHub packages into a local runtime workspace.

    - ``enable`` / ``disable`` maintain an enabled id list under work_root
    - ``prompt_pack`` materializes system prompts for agent injection
    - ``run`` optionally calls an LLM with skill as system + user task
    """

    def __init__(
        self,
        catalog: SkillCatalog,
        *,
        work_root: Path,
        llm_caller: Callable[[str, str], str] | None = None,
    ) -> None:
        self.catalog = catalog
        self.work_root = Path(work_root)
        self.work_root.mkdir(parents=True, exist_ok=True)
        self.enabled_path = self.work_root / "enabled.json"
        self.packs_dir = self.work_root / "packs"
        self.packs_dir.mkdir(parents=True, exist_ok=True)
        self.runs_dir = self.work_root / "runs"
        self.runs_dir.mkdir(parents=True, exist_ok=True)
        self.llm_caller = llm_caller

    def _read_enabled(self) -> list[str]:
        if not self.enabled_path.is_file():
            return []
        try:
            data = json.loads(self.enabled_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return []
        if isinstance(data, list):
            return [str(x) for x in data]
        if isinstance(data, dict):
            return [str(x) for x in data.get("enabled") or []]
        return []

    def _write_enabled(self, ids: list[str]) -> None:
        uniq = sorted(set(ids))
        self.enabled_path.write_text(
            json.dumps({"enabled": uniq, "updated_at": _utc_iso()}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def list_enabled(self) -> list[str]:
        return self._read_enabled()

    def enable(self, skill_id: str) -> SkillPackage:
        pkg = self.catalog.load(skill_id)
        ids = self._read_enabled()
        if skill_id not in ids:
            ids.append(skill_id)
            self._write_enabled(ids)
        return pkg

    def disable(self, skill_id: str) -> None:
        ids = [x for x in self._read_enabled() if x != skill_id]
        self._write_enabled(ids)

    def load_enabled(self) -> list[SkillPackage]:
        out: list[SkillPackage] = []
        for sid in self._read_enabled():
            try:
                out.append(self.catalog.load(sid))
            except KeyError:
                continue
        return out

    def compose_system(self, skill_ids: list[str] | None = None, *, max_chars: int = 14000) -> str:
        ids = skill_ids if skill_ids is not None else self._read_enabled()
        if not ids:
            return ""
        parts: list[str] = ["# Enabled Skills\n"]
        budget = max_chars
        for sid in ids:
            try:
                pkg = self.catalog.load(sid)
            except KeyError:
                continue
            chunk = pkg.system_prompt(max_chars=min(6000, budget))
            if len(chunk) + 2 > budget:
                break
            parts.append(chunk)
            parts.append("\n---\n")
            budget -= len(chunk) + 5
        return "\n".join(parts).strip()

    def materialize_pack(self, skill_id: str) -> Path:
        pkg = self.catalog.load(skill_id)
        pack_id = f"{skill_id}-{uuid.uuid4().hex[:6]}"
        dest = self.packs_dir / pack_id
        dest.mkdir(parents=True, exist_ok=True)
        (dest / "meta.json").write_text(
            json.dumps(pkg.meta.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        (dest / "SYSTEM.md").write_text(pkg.system_prompt(), encoding="utf-8")
        (dest / "SKILL.md").write_text(
            Path(pkg.meta.path).read_text(encoding="utf-8", errors="replace"),
            encoding="utf-8",
        )
        return dest

    def run(
        self,
        skill_id: str,
        task: str,
        *,
        use_llm: bool = False,
    ) -> dict[str, Any]:
        pkg = self.catalog.load(skill_id)
        system = pkg.system_prompt()
        run_id = f"skrun-{uuid.uuid4().hex[:8]}"
        row: dict[str, Any] = {
            "id": run_id,
            "skill_id": skill_id,
            "task": task,
            "ts": _utc_iso(),
            "system_chars": len(system),
            "use_llm": use_llm,
            "ok": True,
            "output": "",
            "error": "",
            "mode": "prompt_pack",
        }
        pack = self.materialize_pack(skill_id)
        row["pack_dir"] = str(pack)
        if use_llm:
            if self.llm_caller is None:
                row["ok"] = False
                row["error"] = "no llm_caller configured"
                row["mode"] = "llm_missing"
            else:
                try:
                    row["output"] = self.llm_caller(system, task)
                    row["mode"] = "llm"
                except Exception as exc:  # noqa: BLE001
                    row["ok"] = False
                    row["error"] = str(exc)
                    row["mode"] = "llm_error"
        else:
            # Offline bind: write task + system for agent pickup
            (pack / "TASK.md").write_text(task, encoding="utf-8")
            row["output"] = f"materialized pack at {pack}"
            row["mode"] = "prompt_pack"
        out = self.runs_dir / f"{run_id}.json"
        out.write_text(json.dumps(row, ensure_ascii=False, indent=2), encoding="utf-8")
        row["run_path"] = str(out)
        return row

    def list_scripts(self, skill_id: str) -> list[str]:
        pkg = self.catalog.load(skill_id)
        return list_skill_scripts(Path(pkg.meta.path).parent)

    def run_script(
        self,
        skill_id: str,
        script: str,
        *,
        args: list[str] | None = None,
        timeout_s: float = 30.0,
        allow_net: bool = False,
    ) -> ScriptRunResult:
        pkg = self.catalog.load(skill_id)
        skill_dir = Path(pkg.meta.path).parent
        result = run_skill_script(
            skill_dir,
            script,
            skill_id=skill_id,
            args=args,
            timeout_s=timeout_s,
            allow_net=allow_net,
        )
        run_id = f"skscript-{uuid.uuid4().hex[:8]}"
        path = self.runs_dir / f"{run_id}.json"
        path.write_text(
            json.dumps(result.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return result
