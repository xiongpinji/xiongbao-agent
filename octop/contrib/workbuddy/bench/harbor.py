# SPDX-License-Identifier: MIT
"""Harbor / Docker bridge for WorkBuddy Bench (stdlib).

Full upstream Harbor scoring needs Python ≥3.12 + ``uv sync`` in
``vendor/workbuddy-bench``. This module provides:

1. Docker availability probe
2. Dataset / task inventory + structural validation
3. Optional ``docker build`` smoke for one task environment
4. Clear status when full Harbor CLI is not yet installed
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


def project_root() -> Path:
    return Path(__file__).resolve().parents[4]


def datasets_root(root: Path | None = None) -> Path:
    return (root or project_root()) / "vendor" / "workbuddy-bench" / "datasets"


def bench_pkg_root(root: Path | None = None) -> Path:
    return (root or project_root()) / "vendor" / "workbuddy-bench"


SUBSET_DIRS = {
    "office": "wb-bench-office-v1.0",
    "code": "wb-bench-code-v1.0",
    "web": "wb-bench-web-v1.0",
    "sec": "wb-bench-sec-v1.0",
}


@dataclass
class HarborStatus:
    docker_available: bool
    docker_version: str = ""
    python_ok_for_harbor: bool = False
    python_version: str = ""
    uv_available: bool = False
    bench_synced: bool = False
    subsets: dict[str, dict[str, Any]] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "docker_available": self.docker_available,
            "docker_version": self.docker_version,
            "python_ok_for_harbor": self.python_ok_for_harbor,
            "python_version": self.python_version,
            "uv_available": self.uv_available,
            "bench_synced": self.bench_synced,
            "subsets": self.subsets,
            "notes": list(self.notes),
        }


def _run(argv: list[str], *, timeout: float = 30.0) -> tuple[int, str, str]:
    try:
        proc = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        return proc.returncode, proc.stdout or "", proc.stderr or ""
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError) as exc:
        return 1, "", str(exc)


def docker_available() -> tuple[bool, str]:
    if not shutil.which("docker"):
        return False, ""
    code, out, err = _run(["docker", "version", "--format", "{{.Server.Version}}"])
    ver = (out or err or "").strip()
    return code == 0 and bool(ver), ver


def harbor_status(root: Path | None = None) -> HarborStatus:
    root = root or project_root()
    docker_ok, docker_ver = docker_available()
    py_ver = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    py_ok = sys.version_info >= (3, 12)
    uv_ok = bool(shutil.which("uv"))
    bench = bench_pkg_root(root)
    synced = (bench / ".venv").is_dir() or (bench / "uv.lock").is_file() and uv_ok and py_ok

    status = HarborStatus(
        docker_available=docker_ok,
        docker_version=docker_ver,
        python_ok_for_harbor=py_ok,
        python_version=py_ver,
        uv_available=uv_ok,
        bench_synced=bool((bench / ".venv").is_dir()),
    )
    ds = datasets_root(root)
    for key, dirname in SUBSET_DIRS.items():
        tasks_dir = ds / dirname / "tasks"
        if tasks_dir.is_dir():
            tasks = [p for p in tasks_dir.iterdir() if p.is_dir()]
            status.subsets[key] = {
                "present": True,
                "tasks": len(tasks),
                "path": str(tasks_dir),
            }
        else:
            status.subsets[key] = {"present": False, "tasks": 0, "path": str(tasks_dir)}

    if not docker_ok:
        status.notes.append("Docker daemon not available — Harbor scoring blocked")
    if not py_ok:
        status.notes.append(
            f"Full Harbor CLI needs Python ≥3.12 (current {py_ver}); "
            "use docker build-smoke + llm_lite until upgraded"
        )
    if not uv_ok:
        status.notes.append("uv not on PATH — cannot `uv sync` vendor/workbuddy-bench yet")
    if synced and not status.bench_synced:
        status.notes.append("uv.lock present; run `uv sync` inside vendor/workbuddy-bench")
    return status


def list_tasks(subset: str, *, root: Path | None = None, limit: int = 0) -> list[dict[str, Any]]:
    key = subset.strip().lower()
    if key not in SUBSET_DIRS:
        raise ValueError(f"unknown subset: {subset}")
    tasks_dir = datasets_root(root) / SUBSET_DIRS[key] / "tasks"
    if not tasks_dir.is_dir():
        return []
    rows: list[dict[str, Any]] = []
    for p in sorted(tasks_dir.iterdir()):
        if not p.is_dir():
            continue
        dockerfile = p / "environment" / "Dockerfile"
        instruction = p / "instruction.md"
        rows.append(
            {
                "task_id": p.name,
                "path": str(p),
                "has_dockerfile": dockerfile.is_file(),
                "has_instruction": instruction.is_file(),
                "has_tests": (p / "tests").is_dir(),
            }
        )
        if limit and len(rows) >= limit:
            break
    return rows


def validate_task(task_dir: Path) -> dict[str, Any]:
    task_dir = Path(task_dir)
    checks = {
        "instruction.md": (task_dir / "instruction.md").is_file(),
        "task.toml": (task_dir / "task.toml").is_file(),
        "environment/Dockerfile": (task_dir / "environment" / "Dockerfile").is_file(),
        "tests/": (task_dir / "tests").is_dir(),
    }
    ok = all(checks.values())
    return {"task_id": task_dir.name, "ok": ok, "checks": checks, "path": str(task_dir)}


def docker_build_smoke(
    task_dir: Path,
    *,
    tag: str | None = None,
    timeout: float = 600.0,
) -> dict[str, Any]:
    """Build the task Dockerfile once to prove Harbor environment packaging."""
    task_dir = Path(task_dir)
    env_dir = task_dir / "environment"
    dockerfile = env_dir / "Dockerfile"
    if not dockerfile.is_file():
        return {"ok": False, "error": "Dockerfile missing", "path": str(task_dir)}
    docker_ok, _ = docker_available()
    if not docker_ok:
        return {"ok": False, "error": "docker unavailable", "path": str(task_dir)}
    image = tag or f"wb-harbor-smoke/{task_dir.name.lower()}:local"
    # Avoid pulling huge bases if offline — still attempt build
    argv = ["docker", "build", "-t", image, "-f", str(dockerfile), str(env_dir)]
    code, out, err = _run(argv, timeout=timeout)
    return {
        "ok": code == 0,
        "image": image,
        "returncode": code,
        "stdout_tail": (out or "")[-2000:],
        "stderr_tail": (err or "")[-2000:],
        "path": str(task_dir),
        "cmd": argv,
    }


def harbor_bridge_report(*, root: Path | None = None, subset: str = "office", limit: int = 3) -> dict[str, Any]:
    status = harbor_status(root)
    tasks = list_tasks(subset, root=root, limit=limit)
    validations = [validate_task(Path(t["path"])) for t in tasks]
    return {
        "status": status.to_dict(),
        "subset": subset,
        "sample_tasks": tasks,
        "validations": validations,
        "env_hint": {
            "WB_HARBOR_SKIP_BUILD": os.environ.get("WB_HARBOR_SKIP_BUILD", ""),
            "full_harbor": "cd vendor/workbuddy-bench && uv sync && ./scripts/run.sh … (needs Py≥3.12)",
        },
    }


def harbor_bridge_json(**kwargs: Any) -> str:
    return json.dumps(harbor_bridge_report(**kwargs), ensure_ascii=False, indent=2)
