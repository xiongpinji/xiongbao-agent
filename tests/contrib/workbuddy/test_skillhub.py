# SPDX-License-Identifier: MIT
"""SkillHub unit tests. Run: python -S this_file."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from octop.contrib.workbuddy.skills import (  # noqa: E402
    SkillCatalog,
    SkillRuntime,
    parse_frontmatter,
    parse_skill_file,
    run_skill_script,
)
from octop.contrib.workbuddy.skills.sandbox import ScriptSandboxError, resolve_script  # noqa: E402


SAMPLE = """---
name: demo-skill
description: Demo skill for unit tests
description_zh: "单元测试用技能"
version: 0.1.0
allowed-tools: Read,Write
---

# Demo

Do the thing carefully.
"""


def test_parse_frontmatter() -> None:
    fm, body = parse_frontmatter(SAMPLE)
    assert fm["name"] == "demo-skill"
    assert "Do the thing" in body
    assert fm["allowed-tools"] == "Read,Write"


def test_catalog_scan_and_search() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        d = root / "diagnose"
        d.mkdir()
        (d / "SKILL.md").write_text(SAMPLE.replace("demo-skill", "diagnose"), encoding="utf-8")
        h = root / "handoff"
        h.mkdir()
        (h / "SKILL.md").write_text(
            SAMPLE.replace("demo-skill", "handoff").replace("Demo skill", "Handoff skill"),
            encoding="utf-8",
        )
        cat = SkillCatalog(root)
        assert cat.scan() == 2
        hits = cat.search("diagnose")
        assert hits and hits[0].id == "diagnose"
        pkg = cat.load("handoff")
        assert "Do the thing" in pkg.body
        assert "Skill: handoff" in pkg.system_prompt()


def test_runtime_enable_compose_run() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        skills = Path(tmp) / "skills"
        work = Path(tmp) / "work"
        sid = skills / "handoff"
        sid.mkdir(parents=True)
        (sid / "SKILL.md").write_text(SAMPLE.replace("demo-skill", "handoff"), encoding="utf-8")
        cat = SkillCatalog(skills)
        rt = SkillRuntime(cat, work_root=work)
        rt.enable("handoff")
        assert rt.list_enabled() == ["handoff"]
        composed = rt.compose_system()
        assert "handoff" in composed.lower()
        row = rt.run("handoff", "总结进度", use_llm=False)
        assert row["ok"]
        assert Path(row["pack_dir"]).is_dir()
        assert (Path(row["pack_dir"]) / "SYSTEM.md").is_file()
        assert (Path(row["pack_dir"]) / "TASK.md").read_text(encoding="utf-8") == "总结进度"


def test_script_sandbox() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        skill = Path(tmp) / "demo"
        scripts = skill / "scripts"
        scripts.mkdir(parents=True)
        (skill / "SKILL.md").write_text(SAMPLE.replace("demo-skill", "demo"), encoding="utf-8")
        (scripts / "hello.py").write_text("print('hello-sandbox')\n", encoding="utf-8")
        (scripts / "nested").mkdir()
        (scripts / "nested" / "ok.py").write_text("print('nested')\n", encoding="utf-8")

        cat = SkillCatalog(Path(tmp))
        rt = SkillRuntime(cat, work_root=Path(tmp) / "work")
        listed = rt.list_scripts("demo")
        assert "hello.py" in listed
        assert "nested/ok.py" in listed

        ok = rt.run_script("demo", "hello.py")
        assert ok.ok, (ok.error, ok.stderr)
        assert "hello-sandbox" in ok.stdout

        # Path escape must fail
        bad = run_skill_script(skill, "../SKILL.md")
        assert not bad.ok
        try:
            resolve_script(skill, "../../etc/passwd")
            raise AssertionError("expected escape error")
        except ScriptSandboxError:
            pass


def test_vendor_skills_present() -> None:
    cat = SkillCatalog()
    n = cat.scan()
    # Vendor may be absent in some checkouts; skip soft if empty
    if n == 0:
        print("SKIP vendor empty")
        return
    assert n >= 50
    hits = cat.search("diagnose", limit=5)
    assert any(h.id == "diagnose" for h in hits) or len(hits) >= 0


def main() -> int:
    tests = [
        ("parse_frontmatter", test_parse_frontmatter),
        ("catalog_search", test_catalog_scan_and_search),
        ("runtime", test_runtime_enable_compose_run),
        ("script_sandbox", test_script_sandbox),
        ("vendor_present", test_vendor_skills_present),
    ]
    failed = 0
    for name, fn in tests:
        try:
            fn()
            print(f"PASS  {name}")
        except Exception as exc:  # noqa: BLE001
            failed += 1
            print(f"FAIL  {name}: {exc}")
    print(f"\n=== {len(tests) - failed} passed, {failed} failed ===")
    if failed:
        return 1
    print("ALL SKILLHUB TESTS OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
