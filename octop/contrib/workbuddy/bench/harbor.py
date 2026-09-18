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


def venv_python(root: Path | None = None) -> Path | None:
    """Return workbuddy-bench venv interpreter if present (Windows or POSIX)."""
    bench = bench_pkg_root(root)
    for rel in (Path(".venv") / "Scripts" / "python.exe", Path(".venv") / "bin" / "python"):
        candidate = bench / rel
        if candidate.is_file():
            return candidate
    return None


def venv_python_version(root: Path | None = None) -> str:
    py = venv_python(root)
    if py is None:
        return ""
    code, out, _ = _run([str(py), "-c", "import sys; print('.'.join(map(str, sys.version_info[:3])))"])
    return (out or "").strip() if code == 0 else ""


def harbor_status(root: Path | None = None) -> HarborStatus:
    root = root or project_root()
    docker_ok, docker_ver = docker_available()
    host_ver = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    venv_ver = venv_python_version(root)
    py_ver = venv_ver or host_ver
    py_ok = False
    if venv_ver:
        parts = venv_ver.split(".")
        try:
            py_ok = (int(parts[0]), int(parts[1])) >= (3, 12)
        except (ValueError, IndexError):
            py_ok = False
    else:
        py_ok = sys.version_info >= (3, 12)
    uv_ok = bool(shutil.which("uv"))
    bench = bench_pkg_root(root)
    synced = venv_python(root) is not None

    status = HarborStatus(
        docker_available=docker_ok,
        docker_version=docker_ver,
        python_ok_for_harbor=py_ok,
        python_version=py_ver,
        uv_available=uv_ok,
        bench_synced=synced,
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
            f"Full Harbor CLI needs Python ≥3.12 (current {py_ver or host_ver}); "
            "run: cd vendor/workbuddy-bench && uv sync --python 3.12"
        )
    if not uv_ok:
        status.notes.append("uv not on PATH — cannot `uv sync` vendor/workbuddy-bench yet")
    if (bench / "uv.lock").is_file() and not synced:
        status.notes.append("uv.lock present; run `uv sync --python 3.12` inside vendor/workbuddy-bench")
    if synced and py_ok:
        status.notes.append("Harbor venv ready - dry-run: scripts/dry_run_office_smoke.sh")
    return status


def uv_sync_bench(*, root: Path | None = None, python: str = "3.12", timeout: float = 600.0) -> dict[str, Any]:
    """Run `uv sync --python <ver>` inside vendor/workbuddy-bench."""
    bench = bench_pkg_root(root)
    if not shutil.which("uv"):
        return {"ok": False, "error": "uv not on PATH", "path": str(bench)}
    argv = ["uv", "sync", "--python", python]
    try:
        proc = subprocess.run(
            argv,
            cwd=str(bench),
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError) as exc:
        return {"ok": False, "error": str(exc), "path": str(bench), "cmd": argv}
    return {
        "ok": proc.returncode == 0,
        "returncode": proc.returncode,
        "path": str(bench),
        "cmd": argv,
        "stdout_tail": (proc.stdout or "")[-2000:],
        "stderr_tail": (proc.stderr or "")[-2000:],
        "venv_python": str(venv_python(root) or ""),
        "venv_version": venv_python_version(root),
    }


def harbor_dry_run(
    *,
    root: Path | None = None,
    job: str = "local-openai-cbc-office-smoke",
    timeout: float = 120.0,
) -> dict[str, Any]:
    """Invoke official run.sh --dry-run via Git Bash / bash when available."""
    root = root or project_root()
    bench = bench_pkg_root(root)
    script = bench / "scripts" / "dry_run_office_smoke.sh"
    py = venv_python(root)
    if py is None:
        return {"ok": False, "error": "bench .venv missing — run uv sync first", "path": str(bench)}
    bash = shutil.which("bash")
    git_bash = Path(r"C:\Program Files\Git\bin\bash.exe")
    if git_bash.is_file():
        bash_bin = str(git_bash)
    elif bash:
        bash_bin = bash
    else:
        return {"ok": False, "error": "bash not found (install Git for Windows)", "path": str(bench)}

    env = os.environ.copy()
    env["PYTHON_BIN"] = str(py)
    env.setdefault("WB_LLM_BASE_URL", "http://127.0.0.1:11434/v1")
    env.setdefault("WB_LLM_API_KEY", "ollama")
    # Prefer job-specific dry-run when smoke script is for default job
    if job != "local-openai-cbc-office-smoke" or not script.is_file():
        run_sh = bench / "scripts" / "run.sh"
        argv = [bash_bin, str(run_sh), "--job", job, "--dry-run"]
        # Ensure python3 resolves inside bash
        wrapper = (
            f'python3() {{ "{py.as_posix()}" "$@"; }}; export -f python3; '
            f'cd "{bench.as_posix()}" && bash ./scripts/run.sh --job {job} --dry-run'
        )
        argv = [bash_bin, "-lc", wrapper]
    else:
        argv = [bash_bin, str(script)]

    try:
        proc = subprocess.run(
            argv,
            cwd=str(bench),
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
            env=env,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError) as exc:
        return {"ok": False, "error": str(exc), "cmd": argv, "path": str(bench)}

    out = (proc.stdout or "") + "\n" + (proc.stderr or "")
    ok = proc.returncode == 0 and "Resolved Manifest" in out
    return {
        "ok": ok,
        "returncode": proc.returncode,
        "job": job,
        "cmd": argv,
        "stdout_tail": (proc.stdout or "")[-4000:],
        "stderr_tail": (proc.stderr or "")[-2000:],
        "path": str(bench),
    }

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


def harness_mount_probe(*, root: Path | None = None) -> dict[str, Any]:
    """Detect Harbor harness mount points without running a live score."""
    root = root or project_root()
    bench = bench_pkg_root(root)
    candidates = [
        bench / "harness",
        bench / "src" / "harness",
        bench / "harbor",
        Path("/opt/harbor"),
    ]
    env_mount = (os.environ.get("WB_HARBOR_HARNESS") or "").strip()
    if env_mount:
        candidates.append(Path(env_mount))
    found: list[str] = []
    for c in candidates:
        if c.exists() and str(c) not in {".", ""}:
            found.append(str(c))
    return {
        "ok": True,
        "bench": str(bench),
        "mounts_found": found,
        "venv_python": str(venv_python(root) or ""),
        "score_ready": bool(venv_python(root)) and bool(found or (bench / "scripts" / "run.sh").is_file()),
        "hint": "Live score: ./scripts/run.sh --job <job> (needs Docker + LLM). Use score --dry-run to skip.",
    }


def harbor_score_entry(
    *,
    root: Path | None = None,
    job: str = "local-openai-cbc-office-smoke",
    dry_run: bool = True,
    timeout: float = 120.0,
) -> dict[str, Any]:
    """Optional single-job score entry; default dry_run to avoid long CI."""
    probe = harness_mount_probe(root=root)
    if dry_run:
        return {
            "ok": True,
            "mode": "dry_run",
            "job": job,
            "probe": probe,
            "note": "skipped live Harbor score; pass dry_run=False to invoke run.sh",
        }
    # Live path reuses dry-run harness but without --dry-run flag via bash wrapper
    root = root or project_root()
    bench = bench_pkg_root(root)
    py = venv_python(root)
    if py is None:
        return {"ok": False, "error": "bench .venv missing", "probe": probe}
    bash = shutil.which("bash")
    git_bash = Path(r"C:\Program Files\Git\bin\bash.exe")
    bash_bin = str(git_bash) if git_bash.is_file() else bash
    if not bash_bin:
        return {"ok": False, "error": "bash not found", "probe": probe}
    wrapper = (
        f'python3() {{ "{py.as_posix()}" "$@"; }}; export -f python3; '
        f'cd "{bench.as_posix()}" && bash ./scripts/run.sh --job {job}'
    )
    try:
        proc = subprocess.run(
            [bash_bin, "-lc", wrapper],
            cwd=str(bench),
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError) as exc:
        return {"ok": False, "error": str(exc), "probe": probe}
    return {
        "ok": proc.returncode == 0,
        "mode": "live",
        "job": job,
        "returncode": proc.returncode,
        "stdout_tail": (proc.stdout or "")[-3000:],
        "stderr_tail": (proc.stderr or "")[-1500:],
        "probe": probe,
    }
