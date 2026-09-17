# SPDX-License-Identifier: MIT
#
"""Tests for the wb2octop converter."""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import pytest

# Ensure contrib/workbuddy on path so we can import it standalone
PROJECT_ROOT = Path(__file__).resolve().parents[3]
OCTOP_DIR = PROJECT_ROOT
sys.path.insert(0, str(OCTOP_DIR))

from octop.contrib.workbuddy import WorkBuddyConverter  # noqa: E402
from octop.contrib.workbuddy.converter import (  # noqa: E402
    _build_manifest,
    _icon_from_category,
    _color_from_category,
    _normalize_prompt,
    CATEGORY_LABELS,
)
from octop.contrib.workbuddy.models import ConvertReport, ExpertConvertResult  # noqa: E402


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def wb_entry_sample():
    """A representative WorkBuddy entry as found in manifest.json."""
    return {
        "id": "UiDesigner",
        "categoryId": "01-ProductDesign",
        "displayName": {"en": "Sam", "zh": "像素君"},
        "profession": {"en": "UI Designer", "zh": "UI设计师"},
        "description": {"en": "Screens 9am sharp.", "zh": "精通设计系统。"},
        "promptFile": "/plugins/ui-designer/agents/ui-designer.md",
        "avatar": "/avatars/UiDesigner.png",
        "createdAt": "2026-03-13T00:00:00Z",
        "updatedAt": "2026-05-21T13:29:23Z",
        "defaultInitPrompt": {
            "zh": "设计一个 UI 界面", "en": "Design a UI",
        },
        "expertType": "agent",
        "agentName": "ui-designer",
        "plugin": "ui-designer",
        "tags": [
            {"zh": "设计系统", "en": "Design System"},
        ],
        "quickPrompts": [
            {"zh": "画一个按钮", "en": "draw a button"},
        ],
    }


@pytest.fixture()
def tmp_vendor(tmp_path: Path, wb_entry_sample):
    """
    Build a synthetic vendor/ tree mirroring the real one, but
    containing only one expert entry.
    """
    vendor_root = tmp_path / "vendor"
    experts_dir = vendor_root / "workbuddy-experts" / "experts"
    experts_dir.mkdir(parents=True)

    # Write the prompt file under prompts/plugins/<plugin>/agents/<id>.md
    prompts_root = experts_dir / "prompts" / "plugins" / "ui-designer" / "agents"
    prompts_root.mkdir(parents=True)
    prompt_file = prompts_root / "ui-designer.md"
    prompt_file.write_text(
        "# Sam the UI Designer\n\nYou are Sam. Always start with empathy.\n",
        encoding="utf-8",
    )

    # Avatars dir (empty in test fixture)
    avatars_dir = experts_dir / "avatars"
    avatars_dir.mkdir()

    # Write manifest
    manifest = {
        "version": "1.0.0",
        "experts": [wb_entry_sample],
    }
    (experts_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    return vendor_root


# ---------------------------------------------------------------------------
# Unit tests for helper functions
# ---------------------------------------------------------------------------

class TestNormalizePrompt:
    def test_strip_trailing_whitespace_and_ensure_newline(self):
        assert _normalize_prompt("hi\n\n\n   \n") == "hi\n"
        assert _normalize_prompt("hi") == "hi\n"
        assert _normalize_prompt("") == ""


class TestCategoryMapping:
    def test_known_categories_present(self):
        for cid in CATEGORY_LABELS:
            assert _icon_from_category(cid)
            assert _color_from_category(cid).startswith("#")

    def test_unknown_category_returns_fallback(self):
        assert _icon_from_category("99-XYZ") == "user"
        assert _color_from_category("99-XYZ") == "#64748b"


class TestBuildManifest:
    def test_basic_manifest_structure(self, wb_entry_sample):
        m = _build_manifest(wb_entry_sample)
        assert m["id"] == "UiDesigner"
        assert m["label"]["zh"] == "像素君"
        assert m["label"]["en"] == "Sam"
        assert m["description"]["zh"] == "精通设计系统。"
        assert m["description"]["en"] == "Screens 9am sharp."
        assert m["icon_name"] == "pen-tool"
        assert m["color"] == "#8b5cf6"
        assert m["prompt_files"] == ["SOUL.md"]
        # Tags carried through
        assert m["_wb"]["tags"][0]["zh"] == "设计系统"
        assert m["_wb"]["expert_type"] == "agent"

    def test_team_kind_gets_no_extra_prompt_files(self, wb_entry_sample):
        wb_entry_sample["expertType"] = "team"
        wb_entry_sample["id"] = "CloudOpsTeam"
        m = _build_manifest(wb_entry_sample)
        assert m["prompt_files"] == ["SOUL.md"]

    def test_quick_prompts_capped_at_six(self, wb_entry_sample):
        wb_entry_sample["quickPrompts"] = [
            {"zh": str(i), "en": str(i)} for i in range(20)
        ]
        m = _build_manifest(wb_entry_sample)
        assert len(m["quick_prompts"]) == 6


# ---------------------------------------------------------------------------
# Integration test (real converter)
# ---------------------------------------------------------------------------

class TestWorkBuddyConverter:
    def test_convert_one_expert(self, tmp_vendor, tmp_path):
        out_dir = tmp_path / "library"
        cvt = WorkBuddyConverter(
            vendor_root=tmp_vendor,
            octop_root=out_dir,
        )
        report = cvt.batch_convert()
        assert report.total == 1
        assert report.succeeded == 1
        assert report.agents_converted == 1

        expert_dir = out_dir / "UiDesigner"
        assert expert_dir.is_dir()
        assert (expert_dir / "manifest.json").is_file()
        assert (expert_dir / "SOUL.md").is_file()
        assert (expert_dir / "IDENTITY.md").is_file()
        assert (expert_dir / "USER.md").is_file()
        assert (expert_dir / "HEARTBEAT.md").is_file()

        manifest = json.loads(
            (expert_dir / "manifest.json").read_text(encoding="utf-8")
        )
        assert manifest["id"] == "UiDesigner"
        assert manifest["_wb"]["expert_type"] == "agent"

        soul = (expert_dir / "SOUL.md").read_text(encoding="utf-8")
        assert "Sam the UI Designer" in soul
        assert "专家定义从 WorkBuddy expert manifest 转换而来" in soul

    def test_skip_missing_when_skip_missing_true(self, tmp_vendor, tmp_path):
        out_dir = tmp_path / "library"
        # Remove the prompt file to simulate missing
        prompt_file = tmp_vendor / "workbuddy-experts" / "experts" / "prompts" / "plugins" / "ui-designer" / "agents" / "ui-designer.md"
        prompt_file.unlink()
        cvt = WorkBuddyConverter(
            vendor_root=tmp_vendor,
            octop_root=out_dir,
        )
        report = cvt.batch_convert()
        assert report.total == 1
        assert report.succeeded == 1
        assert report.skipped == 1
        assert report.failed == 0

    def test_fail_missing_when_skip_missing_false(self, tmp_vendor, tmp_path):
        out_dir = tmp_path / "library"
        prompt_file = tmp_vendor / "workbuddy-experts" / "experts" / "prompts" / "plugins" / "ui-designer" / "agents" / "ui-designer.md"
        prompt_file.unlink()
        cvt = WorkBuddyConverter(
            vendor_root=tmp_vendor,
            octop_root=out_dir,
            skip_missing=False,
        )
        report = cvt.batch_convert()
        assert report.total == 1
        assert report.succeeded == 0
        assert report.failed == 1

    def test_filter_by_kind(self, tmp_vendor, tmp_path):
        # Modify entry to plugin kind
        manifest_path = tmp_vendor / "workbuddy-experts" / "experts" / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["experts"][0]["expertType"] = "plugin"
        manifest["experts"].append({
            **manifest["experts"][0],
            "id": "Other",
            "agentName": "other",
        })
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")

        out_dir = tmp_path / "library"
        cvt = WorkBuddyConverter(vendor_root=tmp_vendor, octop_root=out_dir)
        report_plugin_only = cvt.batch_convert(filter_kind="plugin")
        assert report_plugin_only.total == 2
        assert report_plugin_only.plugins_converted == 2
        report_agent_only = cvt.batch_convert(filter_kind="agent")
        assert report_agent_only.total == 0
