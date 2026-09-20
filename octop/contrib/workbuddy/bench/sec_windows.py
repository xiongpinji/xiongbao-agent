"""Harbor sec-full Windows-safe wrapper.

P1-2 deliverable. The full security subset (``wb-bench-sec-v1.0``) lives under
the project tree, which on Windows easily exceeds ``MAX_PATH`` (260 chars)
once a docker build context, ``-f <Dockerfile>``, and a tag are appended to
the command line. Chinese characters in the project root double the visual
length, and Windows ``docker build`` rejects the call long before the
8 KiB ``CreateProcess`` limit is hit.

This module exposes:

* ``sec_full_iter_tasks`` — iterates every sec task without invoking docker,
  so callers can pre-validate, skip, or partition the workload.
* ``sec_full_windows_paths`` — returns the ``Dockerfile`` / context paths
  with their actual byte / char lengths and the recommended short root
  (``WB_BENCH_ROOT`` or ``C:\\wbbench`` junction).
* ``sec_full_short_root_diagnostics`` — returns enough information for an
  operator to set up the short-junction mitigation: existing junction
  state, suggested command, expected savings.
* ``sec_full_build`` — invokes ``docker build`` for one task using the
  short root when one is configured. Falls back to the native path with a
  warning so a Linux / macOS operator still works.

The wrapper never silently fails — every docker invocation returns a
structured result so the bench runner can persist it.

This module is Windows-aware but cross-platform: on POSIX it is a thin
forwarder around the underlying ``subprocess.run``.

Usage::

    python -m octop.contrib.workbuddy.bench.sec_windows diagnostics
    python -m octop.contrib.workbuddy.bench.sec_windows paths --limit 20
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path

_MAX_WINDOWS_PATH = 260
"""``MAX_PATH`` ceiling before the long-path prefix is required."""

_DOCKER_CMD_BUFFER = 64
"""Reserved slack for ``docker build -f … -t … <ctx>`` argument bytes."""


@dataclass(frozen=True)
class TaskPathInfo:
    task_id: str
    dockerfile_native: str
    context_native: str
    dockerfile_len: int
    context_len: int
    exceeds_max_path: bool
    short_dockerfile: str | None
    short_context: str | None

    def to_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "dockerfile_native": self.dockerfile_native,
            "context_native": self.context_native,
            "dockerfile_len": self.dockerfile_len,
            "context_len": self.context_len,
            "exceeds_max_path": self.exceeds_max_path,
            "short_dockerfile": self.short_dockerfile,
            "short_context": self.short_context,
        }


@dataclass
class ShortRootDiagnostics:
    env_var: str
    configured_root: str | None
    native_root: str
    native_root_len: int
    recommendation: str
    setup_command: str | None
    expected_savings_chars: int
    issues: list[str] = field(default_factory=list)
    tasks_total: int = 0
    tasks_at_risk: int = 0

    def to_dict(self) -> dict:
        return {
            "env_var": self.env_var,
            "configured_root": self.configured_root,
            "native_root": self.native_root,
            "native_root_len": self.native_root_len,
            "recommendation": self.recommendation,
            "setup_command": self.setup_command,
            "expected_savings_chars": self.expected_savings_chars,
            "issues": list(self.issues),
            "tasks_total": self.tasks_total,
            "tasks_at_risk": self.tasks_at_risk,
        }


def _is_windows() -> bool:
    return sys.platform == "win32" or sys.platform.startswith("cygwin")


def _short_root_or_none() -> str | None:
    """Return the configured WB_BENCH_ROOT (stripped) or None."""
    raw = (os.environ.get("WB_BENCH_ROOT") or "").strip()
    return raw or None


def _import_datasets_root():
    """Import ``datasets_root`` from harbor module (works in package and script)."""
    try:
        from .harbor import datasets_root  # type: ignore

        return datasets_root
    except ImportError:
        # Fallback: parent of this file is bench/, harbor.py lives there.
        import importlib.util as _ilu

        here = Path(__file__).resolve().parent
        spec = _ilu.spec_from_file_location("_harbor_mod", here / "harbor.py")
        if not spec or not spec.loader:
            raise
        mod = _ilu.module_from_spec(spec)
        sys.modules["_harbor_mod"] = mod  # dataclasses needs the module registered
        spec.loader.exec_module(mod)  # type: ignore[union-attr]
        return mod.datasets_root


def sec_root(*, project_root: Path | None = None) -> Path:
    """Locate the sec dataset root, honoring ``WB_BENCH_ROOT``."""
    datasets_root = _import_datasets_root()

    if _short_root_or_none():
        return Path(_short_root_or_none()) / "datasets" / "wb-bench-sec-v1.0"
    return datasets_root(project_root) / "wb-bench-sec-v1.0"


def sec_full_iter_tasks(root: Path | None = None) -> Iterator[Path]:
    """Yield each sec task directory. Never invokes docker."""
    base = root or sec_root()
    tasks = base / "tasks"
    if not tasks.is_dir():
        return
    for p in sorted(tasks.iterdir()):
        if p.is_dir():
            yield p


def sec_full_windows_paths(root: Path | None = None) -> list[TaskPathInfo]:
    """Return per-task path diagnostics. Cross-platform: works on POSIX too.

    ``exceeds_max_path`` is True when the docker build command line, padded
    with ``docker build -f <Dockerfile> -t <tag> <context>`` arguments,
    would overflow ``MAX_PATH``. Only meaningful on Windows, but always
    computed so dashboards can surface the data.
    """
    out: list[TaskPathInfo] = []
    short = _short_root_or_none()
    for task in sec_full_iter_tasks(root):
        dockerfile = task / "environment" / "Dockerfile"
        context = task / "environment"
        df_native = str(dockerfile)
        ctx_native = str(context)
        df_short = None
        ctx_short = None
        if short:
            try:
                # When the caller passes ``root`` we treat it as the sec
                # dataset root and compute ``rel`` against it. Otherwise
                # fall back to ``sec_root()`` which honors WB_BENCH_ROOT.
                sec_root_path = root if root is not None else sec_root()
                rel = task.relative_to(sec_root_path)
                df_short = str(
                    Path(short)
                    / "datasets"
                    / "wb-bench-sec-v1.0"
                    / rel
                    / "environment"
                    / "Dockerfile"
                )
                ctx_short = str(
                    Path(short) / "datasets" / "wb-bench-sec-v1.0" / rel / "environment"
                )
            except ValueError:
                # task isn't under the configured short root; leave None.
                pass
        df_len = len(df_native)
        ctx_len = len(ctx_native)
        exceeds = _is_windows() and (
            df_len + _DOCKER_CMD_BUFFER > _MAX_WINDOWS_PATH
            or ctx_len + _DOCKER_CMD_BUFFER > _MAX_WINDOWS_PATH
        )
        out.append(
            TaskPathInfo(
                task_id=task.name,
                dockerfile_native=df_native,
                context_native=ctx_native,
                dockerfile_len=df_len,
                context_len=ctx_len,
                exceeds_max_path=exceeds,
                short_dockerfile=df_short,
                short_context=ctx_short,
            )
        )
    return out


def sec_full_short_root_diagnostics(root: Path | None = None) -> ShortRootDiagnostics:
    """Tell operators what to do to make sec-full work on Windows."""
    datasets_root = _import_datasets_root()

    native_root = str((root or datasets_root()).parent)
    short = _short_root_or_none()
    issues: list[str] = []
    configured_root = None
    setup_command = None
    expected_savings = 0
    recommendation = "No action required."
    if not _is_windows():
        return ShortRootDiagnostics(
            env_var="WB_BENCH_ROOT",
            configured_root=short,
            native_root=native_root,
            native_root_len=len(native_root),
            recommendation="POSIX environment; sec-full runs without short root.",
            setup_command=None,
            expected_savings_chars=0,
            issues=issues,
            tasks_total=0,
            tasks_at_risk=0,
        )
    paths = sec_full_windows_paths(root)
    tasks_at_risk = sum(1 for r in paths if r.exceeds_max_path)
    if short:
        configured_root = short
        if not Path(short).exists():
            issues.append(f"WB_BENCH_ROOT points at {short} but the directory does not exist.")
            recommendation = (
                "Run the suggested mklink command, or copy the sec dataset there, then "
                "rerun the bench."
            )
        else:
            recommendation = (
                f"WB_BENCH_ROOT already configured to {short}; "
                f"{tasks_at_risk} task(s) still exceed MAX_PATH — consider an even shorter root."
            )
    else:
        # Build a recommendation using a Windows mklink command targeting a short path.
        # C:\wbbench is the canonical suggestion in harbor.py.
        junction = r"C:\wbbench"
        setup_command = (
            f'mklink /J "{junction}" "{native_root}\\.."'
        )
        expected_savings = max(0, len(native_root) - len(junction) - 4)
        recommendation = (
            f"Set WB_BENCH_ROOT to a short junction (suggested: {junction}). "
            f"Expected savings: ~{expected_savings} chars per path. "
            f"{tasks_at_risk} task(s) currently at risk."
        )
    return ShortRootDiagnostics(
        env_var="WB_BENCH_ROOT",
        configured_root=configured_root,
        native_root=native_root,
        native_root_len=len(native_root),
        recommendation=recommendation,
        setup_command=setup_command,
        expected_savings_chars=expected_savings,
        issues=issues,
        tasks_total=len(paths),
        tasks_at_risk=tasks_at_risk,
    )


def _select_paths(info: TaskPathInfo, *, prefer_short: bool) -> tuple[str, str]:
    """Pick (dockerfile, context) honoring ``WB_BENCH_ROOT`` when present."""
    if prefer_short and info.short_dockerfile and info.short_context:
        return info.short_dockerfile, info.short_context
    return info.dockerfile_native, info.context_native


def sec_full_build(
    task_id: str,
    *,
    tag: str | None = None,
    timeout: float = 600.0,
    skip_if_risky: bool = True,
    root: Path | None = None,
) -> dict:
    """Run ``docker build`` for one sec task. Returns a structured result.

    ``skip_if_risky`` (default True) short-circuits with a structured error
    instead of attempting a build that we know will fail on Windows. Set
    False to force the call when running in a container that already
    has long-path support.
    """
    info_map = {p.task_id: p for p in sec_full_windows_paths(root)}
    info = info_map.get(task_id)
    if info is None:
        return {"ok": False, "error": f"unknown task: {task_id}", "path": task_id}
    if skip_if_risky and info.exceeds_max_path and not info.short_dockerfile:
        return {
            "ok": False,
            "error": "MAX_PATH at risk; rerun with WB_BENCH_ROOT set",
            "task_id": task_id,
            "diagnostics": sec_full_short_root_diagnostics(root).to_dict(),
            "path": info.dockerfile_native,
        }
    if not shutil.which("docker"):
        return {"ok": False, "error": "docker unavailable", "task_id": task_id}
    prefer_short = bool(_short_root_or_none()) and not info.exceeds_max_path
    dockerfile, context = _select_paths(info, prefer_short=prefer_short)
    image = tag or f"wb-harbor-sec/{task_id.lower()}:local"
    argv = ["docker", "build", "-f", dockerfile, "-t", image, context]
    try:
        proc = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError) as exc:
        return {
            "ok": False,
            "error": str(exc),
            "task_id": task_id,
            "cmd": argv,
            "path": dockerfile,
        }
    return {
        "ok": proc.returncode == 0,
        "task_id": task_id,
        "image": image,
        "returncode": proc.returncode,
        "stdout_tail": (proc.stdout or "")[-2000:],
        "stderr_tail": (proc.stderr or "")[-2000:],
        "dockerfile": dockerfile,
        "context": context,
        "cmd": argv,
    }


def sec_full_report(*, root: Path | None = None) -> dict:
    """One-shot JSON report suitable for ops dashboards."""
    diags = sec_full_short_root_diagnostics(root)
    paths = sec_full_windows_paths(root)
    return {
        "diagnostics": diags.to_dict(),
        "tasks": [p.to_dict() for p in paths[:50]],  # cap to first 50
        "task_count": len(paths),
    }


def _cli() -> int:
    import argparse

    ap = argparse.ArgumentParser(description="Harbor sec-full Windows diagnostics")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p_diag = sub.add_parser("diagnostics", help="Emit short-root diagnostics")
    p_diag.add_argument("--root", default=None)
    p_paths = sub.add_parser("paths", help="Dump every task's path lengths")
    p_paths.add_argument("--root", default=None)
    p_paths.add_argument("--limit", type=int, default=20)
    args = ap.parse_args()
    if args.cmd == "diagnostics":
        out = sec_full_short_root_diagnostics(Path(args.root) if args.root else None)
        print(json.dumps(out.to_dict(), ensure_ascii=False, indent=2))
    elif args.cmd == "paths":
        rows = sec_full_windows_paths(Path(args.root) if args.root else None)
        rows.sort(key=lambda r: r.dockerfile_len, reverse=True)
        for r in rows[: args.limit]:
            print(json.dumps(r.to_dict(), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(_cli())
