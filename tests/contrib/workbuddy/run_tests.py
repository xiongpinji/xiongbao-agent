"""
Minimal test runner for the converter — runs against the vendored library
without requiring pytest.
"""
import json
import shutil
import sys
import tempfile
from pathlib import Path

PROJECT = Path(r"D:\AI编程库\项目库\进行中的项目\xiongbao agent")
sys.path.insert(0, str(PROJECT))

from octop.contrib.workbuddy import WorkBuddyConverter  # noqa
from octop.contrib.workbuddy.converter import (  # noqa
    _build_manifest,
    _color_from_category,
    _icon_from_category,
    _normalize_prompt,
    CATEGORY_LABELS,
)


passed = []
failed = []

def test(name, fn):
    try:
        fn()
        passed.append(name)
        print(f"PASS  {name}")
    except AssertionError as e:
        failed.append((name, str(e)))
        print(f"FAIL  {name}: {e}")
    except Exception as e:
        failed.append((name, f"{type(e).__name__}: {e}"))
        print(f"ERR   {name}: {e}")


def t_normalize():
    assert _normalize_prompt("hi\n\n\n   \n") == "hi\n"
    assert _normalize_prompt("hi") == "hi\n"
    assert _normalize_prompt("") == ""

def t_categories():
    for cid in CATEGORY_LABELS:
        assert _icon_from_category(cid)
        assert _color_from_category(cid).startswith("#")
    assert _icon_from_category("99-XYZ") == "user"
    assert _color_from_category("99-XYZ") == "#64748b"

def t_build_manifest_agent():
    e = {
        "id": "UiDesigner",
        "categoryId": "01-ProductDesign",
        "displayName": {"en": "Sam", "zh": "像素君"},
        "description": {"en": "Screens 9am sharp.", "zh": "精通设计系统。"},
        "defaultInitPrompt": {"zh": "设计 UI", "en": "Design UI"},
        "expertType": "agent",
        "agentName": "ui-designer",
        "plugin": "ui-designer",
        "tags": [{"zh": "设计系统", "en": "Design System"}],
        "quickPrompts": [{"zh": "画按钮", "en": "draw a button"}],
    }
    m = _build_manifest(e)
    assert m["id"] == "UiDesigner"
    assert m["label"]["zh"] == "像素君"
    assert m["icon_name"] == "pen-tool"
    assert m["_wb"]["expert_type"] == "agent"

def t_build_manifest_team():
    e = {
        "id": "CloudOpsTeam",
        "categoryId": "02-Engineering",
        "displayName": {"en": "Team", "zh": "团队"},
        "description": {"zh": "测试"},
        "defaultInitPrompt": {"zh": ""},
        "expertType": "team",
        "agentName": "t",
        "plugin": "p",
        "tags": [],
        "quickPrompts": [],
    }
    m = _build_manifest(e)
    assert m["prompt_files"] == ["SOUL.md"]

def t_quick_prompts_capped():
    e = {
        "id": "X", "categoryId": "01-ProductDesign",
        "displayName": {"en": "X", "zh": "X"}, "description": {"zh": ""},
        "defaultInitPrompt": {"zh": ""}, "expertType": "agent",
        "agentName": "x", "plugin": "x", "tags": [],
        "quickPrompts": [{"zh": str(i), "en": str(i)} for i in range(20)],
    }
    m = _build_manifest(e)
    assert len(m["quick_prompts"]) == 6


def t_convert_one(tmp):
    """Fresh tmp dir, synthetic vendor tree, full batch_convert of one expert."""
    vendor = Path(tmp) / "vendor"
    edir = vendor / "workbuddy-experts" / "experts"
    edir.mkdir(parents=True)
    prompts = edir / "prompts" / "plugins" / "ui-designer" / "agents"
    prompts.mkdir(parents=True)
    (prompts / "ui-designer.md").write_text(
        "# Sam\n\nYou are Sam the UI designer.\n", encoding="utf-8"
    )
    (edir / "avatars").mkdir()
    (edir / "manifest.json").write_text(
        json.dumps({
            "version": "1.0.0",
            "experts": [{
                "id": "UiDesigner",
                "categoryId": "01-ProductDesign",
                "displayName": {"en": "Sam", "zh": "像素君"},
                "description": {"zh": "x"},
                "promptFile": "/plugins/ui-designer/agents/ui-designer.md",
                "defaultInitPrompt": {"zh": ""},
                "expertType": "agent",
                "agentName": "ui-designer",
                "plugin": "ui-designer",
                "tags": [],
                "quickPrompts": [],
            }],
        }, ensure_ascii=False),
        encoding="utf-8",
    )
    out = Path(tmp) / "lib"
    cvt = WorkBuddyConverter(vendor_root=vendor, octop_root=out)
    report = cvt.batch_convert()
    assert report.total == 1
    assert report.succeeded == 1
    assert (out / "UiDesigner" / "manifest.json").is_file()
    assert (out / "UiDesigner" / "SOUL.md").is_file()
    soul = (out / "UiDesigner" / "SOUL.md").read_text(encoding="utf-8")
    assert "Sam the UI designer" in soul

def t_skip_missing(tmp):
    vendor = Path(tmp) / "v_skip"
    edir = vendor / "workbuddy-experts" / "experts"
    edir.mkdir(parents=True)
    (edir / "avatars").mkdir()
    (edir / "prompts").mkdir()
    (edir / "manifest.json").write_text(
        json.dumps({"experts": [{
            "id": "MissingExpert", "categoryId": "01-ProductDesign",
            "displayName": {"zh": "缺失"},
            "description": {"zh": "x"},
            "promptFile": "/plugins/x/agents/MissingExpert.md",
            "defaultInitPrompt": {"zh": "fallback text"},
            "expertType": "agent", "agentName": "m", "plugin": "x",
            "tags": [], "quickPrompts": [],
        }]}, ensure_ascii=False), encoding="utf-8",
    )
    out = Path(tmp) / "lib_skip"
    cvt = WorkBuddyConverter(vendor_root=vendor, octop_root=out)
    report = cvt.batch_convert()
    print(f"  [debug skip] total={report.total} ok={report.succeeded} skip={report.skipped} fail={report.failed}")
    if report.failed_results():
        for fr in report.failed_results():
            print(f"    fail: {fr.expert_id} {fr.error}")
    assert report.total == 1, f"total expected 1, got {report.total}"
    # "succeeded" counter only counts non-skipped successes. Skipped ones
    # write outputs via the defaultInitPrompt fallback and are tracked
    # in `skipped` instead.
    assert report.skipped == 1, f"skip expected 1, got {report.skipped}"
    assert report.failed == 0, f"fail expected 0, got {report.failed}"

def t_fail_missing(tmp):
    vendor = Path(tmp) / "v_fail"
    edir = vendor / "workbuddy-experts" / "experts"
    edir.mkdir(parents=True)
    (edir / "avatars").mkdir()
    (edir / "prompts").mkdir()
    (edir / "manifest.json").write_text(
        json.dumps({"experts": [{
            "id": "X", "categoryId": "01-ProductDesign",
            "displayName": {"zh": "X"},
            "description": {"zh": "x"},
            "promptFile": "/plugins/x/agents/X.md",
            "defaultInitPrompt": {"zh": ""},
            "expertType": "agent", "agentName": "x", "plugin": "x",
            "tags": [], "quickPrompts": [],
        }]}, ensure_ascii=False), encoding="utf-8",
    )
    out = Path(tmp) / "lib_fail"
    cvt = WorkBuddyConverter(vendor_root=vendor, octop_root=out, skip_missing=False)
    report = cvt.batch_convert()
    assert report.total == 1
    assert report.failed == 1


with tempfile.TemporaryDirectory() as tmp:
    test("normalize_prompt", t_normalize)
    test("categories", t_categories)
    test("build_manifest_agent", t_build_manifest_agent)
    test("build_manifest_team", t_build_manifest_team)
    test("quick_prompts_capped", t_quick_prompts_capped)
    test("convert_one_expert", lambda: t_convert_one(tmp))
    test("skip_missing", lambda: t_skip_missing(tmp))
    test("fail_missing", lambda: t_fail_missing(tmp))

print(f"\n=== {len(passed)} passed, {len(failed)} failed ===")
if failed:
    sys.exit(1)
