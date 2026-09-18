# SPDX-License-Identifier: MIT
"""Allowlisted skill script runner (sandbox-ish, stdlib only).

Safety rules:
- Script path must resolve under ``<skill_dir>/scripts/`` (no ``..`` escape).
- Only ``.py`` / ``.js`` / ``.mjs`` / ``.ts`` / ``.sh`` / ``.ps1`` extensions.
- ``subprocess`` with argv list (never ``shell=True``).
- Hard timeout; stdout/stderr capped.
- Optional ``allow_net=False`` strips proxy env and sets ``NO_NETWORK=1`` hint
  (cannot fully block sockets without OS sandbox; documents intent).
"""

from __future__ import annotations

import os
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Sequence

ALLOWED_SUFFIXES = {".py", ".js", ".mjs", ".ts", ".sh", ".ps1", ".bash"}


class ScriptSandboxError(ValueError):
    pass


@dataclass
class ScriptRunResult:
    ok: bool
    skill_id: str
    script: str
    argv: list[str]
    returncode: int | None
    stdout: str
    stderr: str
    timed_out: bool = False
    error: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def list_skill_scripts(skill_dir: Path) -> list[str]:
    scripts = Path(skill_dir) / "scripts"
    if not scripts.is_dir():
        return []
    out: list[str] = []
    for p in sorted(scripts.rglob("*")):
        if p.is_file() and p.suffix.lower() in ALLOWED_SUFFIXES:
            out.append(p.relative_to(scripts).as_posix())
    return out


def resolve_script(skill_dir: Path, rel: str) -> Path:
    rel = (rel or "").strip().replace("\\", "/")
    if not rel or rel.startswith("/") or ".." in Path(rel).parts:
        raise ScriptSandboxError(f"invalid script path: {rel!r}")
    scripts_root = (Path(skill_dir) / "scripts").resolve()
    if not scripts_root.is_dir():
        raise ScriptSandboxError(f"no scripts/ under {skill_dir}")
    target = (scripts_root / rel).resolve()
    try:
        target.relative_to(scripts_root)
    except ValueError as exc:
        raise ScriptSandboxError(f"script escapes scripts/: {rel}") from exc
    if not target.is_file():
        raise ScriptSandboxError(f"script not found: {rel}")
    if target.suffix.lower() not in ALLOWED_SUFFIXES:
        raise ScriptSandboxError(f"suffix not allowed: {target.suffix}")
    return target


def _interpreter_for(path: Path) -> list[str]:
    suf = path.suffix.lower()
    if suf == ".py":
        return [sys.executable, "-S", str(path)]
    if suf in {".js", ".mjs"}:
        return ["node", str(path)]
    if suf == ".ts":
        return ["npx", "--yes", "tsx", str(path)]
    if suf in {".sh", ".bash"}:
        return ["bash", str(path)]
    if suf == ".ps1":
        return ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(path)]
    raise ScriptSandboxError(f"no interpreter for {suf}")


def run_skill_script(
    skill_dir: Path,
    rel_script: str,
    *,
    skill_id: str = "",
    args: Sequence[str] | None = None,
    timeout_s: float = 30.0,
    cwd: Path | None = None,
    allow_net: bool = False,
    max_output_chars: int = 8000,
    env_extra: dict[str, str] | None = None,
) -> ScriptRunResult:
    """Run one allowlisted script; never raises for process failure (returns ok=False)."""
    sid = skill_id or Path(skill_dir).name
    try:
        script_path = resolve_script(skill_dir, rel_script)
        argv = _interpreter_for(script_path) + [str(a) for a in (args or [])]
    except ScriptSandboxError as exc:
        return ScriptRunResult(
            ok=False,
            skill_id=sid,
            script=rel_script,
            argv=[],
            returncode=None,
            stdout="",
            stderr="",
            error=str(exc),
        )

    work = Path(cwd) if cwd else Path(skill_dir)
    env = os.environ.copy()
    if not allow_net:
        for key in (
            "HTTP_PROXY",
            "HTTPS_PROXY",
            "http_proxy",
            "https_proxy",
            "ALL_PROXY",
            "all_proxy",
        ):
            env.pop(key, None)
        env["NO_NETWORK"] = "1"
    if env_extra:
        env.update(env_extra)

    try:
        proc = subprocess.run(
            argv,
            cwd=str(work),
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_s,
            shell=False,
            check=False,
        )
        out = (proc.stdout or "")[:max_output_chars]
        err = (proc.stderr or "")[:max_output_chars]
        return ScriptRunResult(
            ok=proc.returncode == 0,
            skill_id=sid,
            script=rel_script,
            argv=argv,
            returncode=proc.returncode,
            stdout=out,
            stderr=err,
            error="" if proc.returncode == 0 else f"exit {proc.returncode}",
        )
    except subprocess.TimeoutExpired as exc:
        out = (exc.stdout or "") if isinstance(exc.stdout, str) else ""
        err = (exc.stderr or "") if isinstance(exc.stderr, str) else ""
        return ScriptRunResult(
            ok=False,
            skill_id=sid,
            script=rel_script,
            argv=argv,
            returncode=None,
            stdout=str(out)[:max_output_chars],
            stderr=str(err)[:max_output_chars],
            timed_out=True,
            error=f"timeout after {timeout_s}s",
        )
    except FileNotFoundError as exc:
        return ScriptRunResult(
            ok=False,
            skill_id=sid,
            script=rel_script,
            argv=argv,
            returncode=None,
            stdout="",
            stderr="",
            error=f"interpreter missing: {exc}",
        )
    except OSError as exc:
        return ScriptRunResult(
            ok=False,
            skill_id=sid,
            script=rel_script,
            argv=argv,
            returncode=None,
            stdout="",
            stderr="",
            error=str(exc),
        )
