import sys
from pathlib import Path

# The bench module lives at octop/contrib/workbuddy/bench/, outside the
# installed ``octop`` package. Add the octop root to sys.path so
# ``contrib.workbuddy.bench.sec_windows`` is importable as a regular module
# (the contrib/ tree ships with __init__.py files).
_OCTOP_ROOT = Path(__file__).resolve().parents[3]
if str(_OCTOP_ROOT) not in sys.path:
    sys.path.insert(0, str(_OCTOP_ROOT))

import pytest  # noqa: E402
from contrib.workbuddy.bench.sec_windows import (  # noqa: E402
    sec_full_build,
    sec_full_iter_tasks,
    sec_full_short_root_diagnostics,
    sec_full_windows_paths,
    sec_root,
)


@pytest.fixture()
def fake_sec_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Build a fake sec dataset tree of 3 tasks, one with a long path."""
    sec = tmp_path / "wb-bench-sec-v1.0"
    tasks = sec / "tasks"
    long_task = tasks / ("a" * 60)
    short_task = tasks / "tiny"
    for t in (long_task, short_task):
        env = t / "environment"
        env.mkdir(parents=True)
        (env / "Dockerfile").write_text("FROM scratch\n", encoding="utf-8")
    monkeypatch.delenv("WB_BENCH_ROOT", raising=False)
    return sec


def test_sec_root_honors_wb_bench_root(
    fake_sec_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # ``WB_BENCH_ROOT`` points at the bench root (parent of ``datasets/``);
    # ``sec_root()`` then appends ``datasets/wb-bench-sec-v1.0``.
    monkeypatch.setenv("WB_BENCH_ROOT", str(fake_sec_root.parent))
    assert sec_root() == fake_sec_root.parent / "datasets" / "wb-bench-sec-v1.0"


def test_sec_full_iter_tasks_lists_all(fake_sec_root: Path) -> None:
    ids = [p.name for p in sec_full_iter_tasks(fake_sec_root)]
    assert "tiny" in ids and any(name.startswith("a") for name in ids)
    assert len(ids) == 2


def test_sec_full_windows_paths_native(
    fake_sec_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("WB_BENCH_ROOT", raising=False)
    rows = sec_full_windows_paths(fake_sec_root)
    assert len(rows) == 2
    long = next(r for r in rows if r.task_id.startswith("a"))
    assert long.dockerfile_len > 200
    assert long.short_dockerfile is None


def test_sec_full_windows_paths_short_root(
    fake_sec_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Mirror the production setup: WB_BENCH_ROOT points at the bench root,
    # ``fake_sec_root`` lives at <bench-root>/datasets/wb-bench-sec-v1.0.
    bench_root = fake_sec_root.parents[1]  # the parent that contains ``datasets/``
    monkeypatch.setenv("WB_BENCH_ROOT", str(bench_root))
    rows = sec_full_windows_paths(fake_sec_root)
    long = next(r for r in rows if r.task_id.startswith("a"))
    assert long.short_dockerfile is not None
    assert Path(long.short_dockerfile).is_absolute()


def test_sec_full_short_root_diagnostics_unset(
    fake_sec_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("WB_BENCH_ROOT", raising=False)
    diag = sec_full_short_root_diagnostics(fake_sec_root)
    assert diag.configured_root is None
    assert diag.tasks_total == 2
    assert diag.setup_command is not None
    assert "mklink" in diag.setup_command
    assert diag.expected_savings_chars > 0


def test_sec_full_short_root_diagnostics_set(
    fake_sec_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("WB_BENCH_ROOT", str(fake_sec_root.parent))
    diag = sec_full_short_root_diagnostics(fake_sec_root)
    assert diag.configured_root == str(fake_sec_root.parent)
    assert diag.setup_command is None


def test_sec_full_short_root_diagnostics_set_missing_dir(
    fake_sec_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("WB_BENCH_ROOT", "Z:\\nope\\does-not-exist")
    diag = sec_full_short_root_diagnostics(fake_sec_root)
    assert diag.issues
    assert "does not exist" in diag.issues[0]


def test_sec_full_build_unknown_task(
    fake_sec_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("WB_BENCH_ROOT", raising=False)
    res = sec_full_build("not-a-task", root=fake_sec_root)
    assert res["ok"] is False
    assert "unknown task" in res["error"]


def test_sec_full_build_skips_risky_task(
    fake_sec_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("WB_BENCH_ROOT", raising=False)
    long_task = next(
        p.name for p in sec_full_iter_tasks(fake_sec_root) if p.name.startswith("a")
    )
    res = sec_full_build(long_task, root=fake_sec_root, skip_if_risky=True)
    if res["ok"]:
        return  # POSIX path
    assert "MAX_PATH" in res["error"] or "docker" in res["error"].lower()


def test_sec_full_build_no_docker(
    fake_sec_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("WB_BENCH_ROOT", raising=False)
    import contrib.workbuddy.bench.sec_windows as mod  # type: ignore

    monkeypatch.setattr(mod.shutil, "which", lambda _: None)
    res = sec_full_build("tiny", root=fake_sec_root, skip_if_risky=False)
    assert res["ok"] is False
    assert "docker unavailable" in res["error"]
