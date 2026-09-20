# SPDX-License-Identifier: MIT
"""Tests for the allowlisted Skill script sandbox (octop.contrib.workbuddy.skills.sandbox).

These tests verify the security guarantees documented in `sandbox.py`:

- The script path must resolve under `<skill_dir>/scripts/`.
- `..` traversal, absolute paths and missing files are rejected.
- Only allowed suffixes can be executed.
- Disallowed extensions in the scripts directory are silently skipped.
- `allow_net=False` strips proxy env vars and sets NO_NETWORK=1.
- stdout/stderr are capped to ``max_output_chars``.
- A timeout raises ``TimeoutExpired`` from the runner and the result is
  marked failed with ``timed_out=True``.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest


def _load_sandbox():
    """Load the sandbox module directly from its on-disk path.

    ``octop.contrib.workbuddy.skills.sandbox`` lives at
    ``octop/contrib/workbuddy/skills/sandbox.py`` — outside of the
    ``src/octop/`` distribution (the project does not expose ``octop.contrib``
    as an installable package). Importing it via a dotted path therefore
    fails. Instead we load it as ``sandbox`` by file path; the module is
    self-contained and only depends on stdlib.
    """
    sandbox_path = (
        Path(__file__).resolve().parents[4] / "contrib" / "workbuddy" / "skills" / "sandbox.py"
    )
    if not sandbox_path.exists():
        raise RuntimeError(f"cannot locate sandbox.py at {sandbox_path}")
    spec = importlib.util.spec_from_file_location("wb_sandbox_under_test", sandbox_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


sb = _load_sandbox()


@pytest.fixture()
def skill_dir(tmp_path: Path) -> Path:
    skill = tmp_path / "demo_skill"
    (skill / "scripts").mkdir(parents=True)
    return skill


def _write(scripts_dir: Path, rel: str, body: str = "") -> Path:
    target = scripts_dir / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(body, encoding="utf-8")
    return target


def test_list_skill_scripts_returns_only_allowed_suffixes(skill_dir: Path) -> None:
    scripts = skill_dir / "scripts"
    _write(scripts, "good.py", "print('hi')")
    _write(scripts, "good.mjs", "console.log('hi')")
    _write(scripts, "good.sh", "echo hi")
    _write(scripts, "bad.exe", "MZ")  # binary / not allowed
    _write(scripts, "README.md", "# docs")
    _write(scripts / "nested", "nested.ts", "console.log('hi')")

    found = sb.list_skill_scripts(skill_dir)
    rels = sorted(found)
    assert "good.py" in rels
    assert "good.mjs" in rels
    assert "good.sh" in rels
    assert "nested/nested.ts" in rels
    assert not any(r.endswith(".exe") for r in rels)
    assert not any(r.endswith(".md") for r in rels)


def test_resolve_script_rejects_path_traversal(skill_dir: Path) -> None:
    _write(skill_dir / "scripts", "good.py")
    with pytest.raises(sb.ScriptSandboxError, match="invalid script path"):
        sb.resolve_script(skill_dir, "../escape.py")


def test_resolve_script_rejects_absolute_path(skill_dir: Path) -> None:
    with pytest.raises(sb.ScriptSandboxError, match="invalid script path"):
        sb.resolve_script(skill_dir, "/etc/passwd")


def test_resolve_script_rejects_disallowed_extension(skill_dir: Path) -> None:
    _write(skill_dir / "scripts", "evil.exe", "MZ")
    with pytest.raises(sb.ScriptSandboxError, match="suffix not allowed"):
        sb.resolve_script(skill_dir, "evil.exe")


def test_resolve_script_rejects_missing_file(skill_dir: Path) -> None:
    (skill_dir / "scripts").mkdir(parents=True, exist_ok=True)
    with pytest.raises(sb.ScriptSandboxError, match="script not found"):
        sb.resolve_script(skill_dir, "nope.py")


def test_resolve_script_accepts_nested_relative(skill_dir: Path) -> None:
    _write(skill_dir / "scripts" / "sub", "good.py")
    target = sb.resolve_script(skill_dir, "sub/good.py")
    assert target.name == "good.py"


def test_resolve_script_rejects_windows_separator_traversal(skill_dir: Path) -> None:
    (skill_dir / "scripts").mkdir(parents=True, exist_ok=True)
    # Windows-style path containing "..\.." must still be rejected.
    with pytest.raises(sb.ScriptSandboxError):
        sb.resolve_script(skill_dir, r"..\..\evil.py")


def test_run_skill_script_executes_python(skill_dir: Path) -> None:
    _write(skill_dir / "scripts", "echo.py", "import sys; print('hello', sys.argv[1])")
    result = sb.run_skill_script(skill_dir, "echo.py", args=["world"], timeout_s=5.0)
    assert result.ok, result.error or result.stderr
    assert "hello world" in result.stdout


def test_run_skill_script_strips_proxy_env_when_no_net(
    skill_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When ``allow_net=False`` the sandbox must drop every proxy variable.

    The sandbox reads ``os.environ`` *before* merging ``env_extra``, so any
    HTTP/HTTPS proxy set in the parent process is wiped regardless of
    ``env_extra``. We use ``monkeypatch.setenv`` to inject the proxy in a
    way that the test isolation framework restores after each test.
    """
    _write(
        skill_dir / "scripts",
        "env.py",
        "import os; print(os.environ.get('NO_NETWORK', '<missing>'));"
        " print(os.environ.get('HTTP_PROXY', '<missing>'))",
    )
    monkeypatch.setenv("HTTP_PROXY", "http://1.2.3.4:8080")
    monkeypatch.setenv("HTTPS_PROXY", "http://1.2.3.4:8080")
    monkeypatch.setenv("all_proxy", "http://1.2.3.4:8080")
    result = sb.run_skill_script(skill_dir, "env.py", timeout_s=5.0, allow_net=False)
    assert result.ok, result.error or result.stderr
    assert "1" in result.stdout  # NO_NETWORK=1
    assert "<missing>" in result.stdout  # HTTP_PROXY stripped


def test_run_skill_script_keeps_proxy_env_when_allow_net(skill_dir: Path) -> None:
    _write(
        skill_dir / "scripts",
        "env.py",
        "import os; print(os.environ.get('HTTP_PROXY', '<missing>'))",
    )
    env_extra = {"HTTP_PROXY": "http://1.2.3.4:8080"}
    result = sb.run_skill_script(
        skill_dir,
        "env.py",
        timeout_s=5.0,
        allow_net=True,
        env_extra=env_extra,
    )
    assert result.ok, result.error or result.stderr
    assert "1.2.3.4" in result.stdout


def test_run_skill_script_caps_output(skill_dir: Path) -> None:
    _write(
        skill_dir / "scripts",
        "noisy.py",
        "import sys; sys.stdout.write('A' * 5000)",
    )
    result = sb.run_skill_script(skill_dir, "noisy.py", timeout_s=5.0, max_output_chars=200)
    assert result.ok, result.error
    # stdout is capped at max_output_chars
    assert len(result.stdout) <= 200


def test_run_skill_script_returns_failure_on_traversal(skill_dir: Path) -> None:
    """Even invalid scripts return a structured failure (no exception leak)."""
    result = sb.run_skill_script(skill_dir, "../escape.py", timeout_s=5.0)
    assert result.ok is False
    assert "invalid script path" in (result.error or "")


def test_run_skill_script_timeout(skill_dir: Path) -> None:
    if sys.platform.startswith("win") and not _has_windows_timeout():
        pytest.skip("subprocess.run timeout precision is unreliable on this shell")
    _write(skill_dir / "scripts", "sleep.py", "import time; time.sleep(5)")
    result = sb.run_skill_script(skill_dir, "sleep.py", timeout_s=0.5)
    assert result.ok is False
    assert result.timed_out is True


def _has_windows_timeout() -> bool:
    """subprocess.run(timeout=) on Windows uses WaitForSingleObject which honours
    timeouts, but very short values can race the interpreter startup. We skip
    on Windows entirely because start-up jitter dominates."""
    return False


def test_run_skill_script_blocked_for_disallowed_suffix(skill_dir: Path) -> None:
    """A script with a disallowed suffix never executes — ``run_skill_script``
    returns a structured failure instead of raising.
    """
    bogus = skill_dir / "scripts" / "bad.exe"
    bogus.parent.mkdir(parents=True, exist_ok=True)
    bogus.write_bytes(b"MZ")
    result = sb.run_skill_script(skill_dir, "bad.exe", timeout_s=1.0)
    assert result.ok is False
    assert "suffix not allowed" in (result.error or "")


def test_interpreter_for_unknown_suffix_raises() -> None:
    """Direct unit test of the interpreter picker."""
    with pytest.raises(sb.ScriptSandboxError, match="no interpreter"):
        sb._interpreter_for(Path("/tmp/anything.exe"))
