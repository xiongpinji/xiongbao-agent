"""
wb2octop converter — WorkBuddy manifest → Octop v1.0.0 expert library.

Input structure (vendor/workbuddy-experts/experts/):
    manifest.json                      ← master list (246 entries, with promptFile paths)
    prompts/plugins/<plugin>/agents/<expert>.md   ← actual prompt text
    avatars/                          ← PNG avatar files (optional)

Output structure (src/octop/infra/agents/experts/library/):
    <id>/
        manifest.json   ← Octop v1.0.0 expert manifest (JSON)
        SOUL.md        ← system prompt body (markdown)
        IDENTITY.md    ← optional identity overrides
        USER.md        ← optional user profile
        HEARTBEAT.md   ← per-turn behaviour guidance
        (skills/       ← embedded skills, if any)
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from .models import ConvertReport, ExpertConvertResult

# ---------------------------------------------------------------------------
# Mapping from WorkBuddy category IDs → Octop expert library category hints
# ---------------------------------------------------------------------------
CATEGORY_LABELS: dict[str, dict[str, str]] = {
    "01-ProductDesign": {"en": "Product Design", "zh": "产品设计"},
    "02-Engineering": {"en": "Engineering", "zh": "技术工程"},
    "03-GameSpatial": {"en": "Game & Spatial", "zh": "游戏与空间计算"},
    "04-DataAI": {"en": "Data & AI", "zh": "数据与人工智能"},
    "05-MarketingGrowth": {"en": "Marketing Growth", "zh": "营销增长"},
    "06-ContentCreative": {"en": "Content Creative", "zh": "内容创作"},
    "07-SalesCommerce": {"en": "Sales Commerce", "zh": "销售商务"},
    "08-FinanceInvestment": {"en": "Finance Investment", "zh": "金融投资"},
    "09-OperationsHR": {"en": "Operations & HR", "zh": "运营与人力资源"},
    "10-ProjectQuality": {"en": "Project & Quality", "zh": "项目管理与质量"},
    "11-SecurityCompliance": {"en": "Security & Compliance", "zh": "法务安全"},
    "12-IndustryConsultant": {"en": "Industry Consultant", "zh": "行业顾问"},
    "13-TencentZone": {"en": "Tencent Zone", "zh": "腾讯专区"},
}


def _normalize_prompt(prompt_text: str) -> str:
    """
    Strip trailing whitespace and ensure the file ends with a newline.

    WorkBuddy prompt files sometimes have trailing whitespace or no final newline,
    which causes unnecessary diff noise in version control.
    """
    if not prompt_text:
        return ""
    return prompt_text.rstrip() + "\n"


# ---------------------------------------------------------------------------
# Template fragments — blended into SOUL.md
# ---------------------------------------------------------------------------

SOUL_TEMPLATE = """\
---
summary: "{summary}"
read_when:
  - 首次启动
  - 手动引导工作区
---

{soul_body}

---

## 来源

本专家定义从 WorkBuddy expert manifest 转换而来（expert id: {expert_id}，
类型: {expert_type}）。原始 prompt 来源见 manifest.json 的 promptFile 字段。
""".strip()


HEARTBEAT_TEMPLATE = """\
---
summary: "每次对话前检查的上下文同步指令"
---

{heartbeat_body}
""".strip()


def _build_manifest(wb_entry: dict) -> dict:
    """
    Build an Octop v1.0.0 expert manifest from a WorkBuddy manifest entry.

    Octop v1.0.0 expert manifest schema:
        id, label (zh/en), description (zh/en), welcome_message (zh/en),
        icon_name, color, prompt_files (list), quick_prompts (list),
        task_examples (optional, zh/en list)
    """
    expert_id = wb_entry.get("id", "")
    kind = wb_entry.get("expertType", "agent")
    category = wb_entry.get("categoryId", "")
    display_name = wb_entry.get("displayName", {})
    if isinstance(display_name, str):
        display_name = {"en": display_name, "zh": display_name}

    description = wb_entry.get("description", {})
    if isinstance(description, str):
        description = {"en": description, "zh": description}

    default_prompt = wb_entry.get("defaultInitPrompt", {})
    if isinstance(default_prompt, str):
        default_prompt = {"en": default_prompt, "zh": default_prompt}

    cat_label = CATEGORY_LABELS.get(category, {"en": category, "zh": category})
    label_en = display_name.get("en", f"Expert {expert_id}")
    label_zh = display_name.get("zh", label_en)

    welcome = wb_entry.get("welcomeMessage", {})
    if isinstance(welcome, str):
        welcome = {"en": welcome, "zh": welcome}

    return {
        "id": expert_id,
        "label": {
            "en": label_en,
            "zh": label_zh,
        },
        "description": {
            "en": description.get("en", ""),
            "zh": description.get("zh", ""),
        },
        "welcome_message": {
            "en": welcome.get("en", default_prompt.get("en", "")),
            "zh": welcome.get("zh", default_prompt.get("zh", "")),
        },
        "icon_name": _icon_from_category(category),
        "color": _color_from_category(category),
        "prompt_files": _prompt_files_for_kind(kind),
        "quick_prompts": _build_quick_prompts(wb_entry),
        "task_examples": {
            "en": default_prompt.get("en", "").split("\n")[:5],
            "zh": default_prompt.get("zh", "").split("\n")[:5],
        },
        # Metadata carried through conversion
        "_wb": {
            "original_id": expert_id,
            "category_id": category,
            "category_label": cat_label,
            "expert_type": kind,
            "agent_name": wb_entry.get("agentName"),
            "plugin": wb_entry.get("plugin"),
            "tags": wb_entry.get("tags", []),
        },
    }


def _prompt_files_for_kind(kind: str) -> list[str]:
    base = ["SOUL.md"]
    if kind == "team":
        return base  # teams share the same layout, extra members added separately
    return base


def _build_quick_prompts(wb_entry: dict) -> list[dict]:
    """Convert WorkBuddy quickPrompts (zh/en pairs) to Octop format."""
    raw_prompts = wb_entry.get("quickPrompts", [])
    result = []
    for qp in raw_prompts[:6]:  # Octop shows up to 6
        if isinstance(qp, dict):
            title = qp.get("title", {})
            desc = qp.get("description", {})
            prompt = qp.get("prompt", {})
            result.append({
                "title": {
                    "en": title.get("en", ""),
                    "zh": title.get("zh", ""),
                },
                "description": {
                    "en": desc.get("en", ""),
                    "zh": desc.get("zh", ""),
                },
                "prompt": {
                    "en": prompt.get("en", ""),
                    "zh": prompt.get("zh", ""),
                },
                "color": qp.get("color", "#f1f5f9"),
                "icon_name": qp.get("icon_name", "star"),
            })
        elif isinstance(qp, str):
            result.append({
                "title": {"en": qp, "zh": qp},
                "description": {"en": "", "zh": ""},
                "prompt": {"en": qp, "zh": qp},
                "color": "#f1f5f9",
                "icon_name": "star",
            })
    return result


def _icon_from_category(cat: str) -> str:
    icons = {
        "01-ProductDesign": "pen-tool",
        "02-Engineering": "code",
        "03-GameSpatial": "gamepad-2",
        "04-DataAI": "brain",
        "05-MarketingGrowth": "trending-up",
        "06-ContentCreative": "edit",
        "07-SalesCommerce": "shopping-cart",
        "08-FinanceInvestment": "trending-up",
        "09-OperationsHR": "users",
        "10-ProjectQuality": "check-circle",
        "11-SecurityCompliance": "shield",
        "12-IndustryConsultant": "briefcase",
        "13-TencentZone": "cloud",
    }
    return icons.get(cat, "user")


def _color_from_category(cat: str) -> str:
    colors = {
        "01-ProductDesign": "#8b5cf6",
        "02-Engineering": "#3b82f6",
        "03-GameSpatial": "#ec4899",
        "04-DataAI": "#10b981",
        "05-MarketingGrowth": "#f59e0b",
        "06-ContentCreative": "#ef4444",
        "07-SalesCommerce": "#6366f1",
        "08-FinanceInvestment": "#e74c3c",
        "09-OperationsHR": "#06b6d4",
        "10-ProjectQuality": "#84cc16",
        "11-SecurityCompliance": "#f97316",
        "12-IndustryConsultant": "#14b8a6",
        "13-TencentZone": "#0ea5e9",
    }
    return colors.get(cat, "#64748b")


# ---------------------------------------------------------------------------
# Main converter
# ---------------------------------------------------------------------------

class WorkBuddyConverter:
    """
    Converts WorkBuddy expert assets into Octop v1.0.0 expert library format.

    Parameters
    ----------
    vendor_root : Path
        Root of the vendor/ directory containing workbuddy-experts/.
        Expected layout::

            vendor_root/
                workbuddy-experts/
                    experts/
                        manifest.json          ← 246-entry master list
                        prompts/
                            plugins/<plugin>/agents/<id>.md
                        avatars/
                            <ExpertId>.png
    octop_root : Path
        Root of the Octop expert library.
        Output will be written to::

            octop_root/<ExpertId>/
                manifest.json
                SOUL.md
                IDENTITY.md   (optional)
                USER.md       (optional)
                HEARTBEAT.md  (optional)
    skip_missing : bool
        If True (default), skip experts whose source prompt file is missing
        (logged as "skipped"). If False, treat missing files as errors.
    dry_run : bool
        If True, compute results but do not write any files.
    """

    def __init__(
        self,
        vendor_root: Path,
        octop_root: Path,
        *,
        skip_missing: bool = True,
        dry_run: bool = False,
    ) -> None:
        self.vendor_root = Path(vendor_root)
        self.octop_root = Path(octop_root)
        self.skip_missing = skip_missing
        self.dry_run = dry_run

        # Derived paths
        self._manifest_path = self.vendor_root / "workbuddy-experts" / "experts" / "manifest.json"
        self._prompts_root = self.vendor_root / "workbuddy-experts" / "experts" / "prompts"
        self._avatars_root = self.vendor_root / "workbuddy-experts" / "experts" / "avatars"

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load_wb_manifest(self) -> dict:
        """Load the WorkBuddy master manifest JSON."""
        if not self._manifest_path.exists():
            raise FileNotFoundError(f"WorkBuddy manifest not found: {self._manifest_path}")
        with open(self._manifest_path, encoding="utf-8") as f:
            return json.load(f)

    def convert_expert(self, wb_entry: dict) -> ExpertConvertResult:
        """
        Convert a single WorkBuddy expert entry into Octop library format.

        Returns an ExpertConvertResult with the outcome.
        """
        expert_id = wb_entry.get("id", "")
        kind = wb_entry.get("expertType", "agent")
        if not expert_id:
            return ExpertConvertResult(
                expert_id="<unknown>",
                kind=kind,
                success=False,
                error="Missing 'id' field in manifest entry",
            )

        # ----------------------------------------------------------------
        # 1. Resolve source prompt file
        # ----------------------------------------------------------------
        prompt_file_rel = wb_entry.get("promptFile", "")
        if prompt_file_rel.startswith("/"):
            prompt_file_rel = prompt_file_rel[1:]

        # WorkBuddy uses "plugins/<plugin>/agents/<id>.md" but our actual
        # files live under "prompts/plugins/<plugin>/agents/<id>.md".
        src_prompt: Path | None = None
        if prompt_file_rel:
            src_prompt = self._prompts_root / prompt_file_rel

        # ----------------------------------------------------------------
        # 2. Load prompt body (if file exists)
        # ----------------------------------------------------------------
        soul_body = ""
        skipped = False

        if src_prompt and src_prompt.exists():
            with open(src_prompt, encoding="utf-8") as f:
                soul_body = _normalize_prompt(f.read())
        else:
            if self.skip_missing:
                skipped = True
                # Use defaultInitPrompt as fallback
                default_prompt = wb_entry.get("defaultInitPrompt", {})
                if isinstance(default_prompt, dict):
                    body_en = default_prompt.get("en", "")
                    body_zh = default_prompt.get("zh", "")
                    soul_body = f"# {wb_entry.get('displayName', {}).get('zh', expert_id)}\n\n{body_en}\n\n{body_zh}\n"
                elif isinstance(default_prompt, str):
                    soul_body = f"# {expert_id}\n\n{default_prompt}\n"
            else:
                return ExpertConvertResult(
                    expert_id=expert_id,
                    kind=kind,
                    success=False,
                    src_path=src_prompt,
                    error=f"Source prompt not found: {src_prompt}",
                )

        # ----------------------------------------------------------------
        # 3. Build Octop manifest
        # ----------------------------------------------------------------
        octop_manifest = _build_manifest(wb_entry)

        # ----------------------------------------------------------------
        # 4. Determine output directory
        # ----------------------------------------------------------------
        dst_dir = self.octop_root / expert_id
        dst_manifest = dst_dir / "manifest.json"
        dst_soul = dst_dir / "SOUL.md"
        dst_identity = dst_dir / "IDENTITY.md"
        dst_user = dst_dir / "USER.md"
        dst_heartbeat = dst_dir / "HEARTBEAT.md"

        # ----------------------------------------------------------------
        # 5. Build SOUL.md content
        # ----------------------------------------------------------------
        display_name = wb_entry.get("displayName", {})
        if isinstance(display_name, str):
            display_name = {"en": display_name, "zh": display_name}

        summary = f"{display_name.get('zh', expert_id)} — {kind} expert"

        soul_content = SOUL_TEMPLATE.format(
            summary=summary,
            soul_body=soul_body,
            expert_id=expert_id,
            expert_type=kind,
        )

        # ----------------------------------------------------------------
        # 6. Build IDENTITY.md (inherited from WorkBuddy plugin field)
        # ----------------------------------------------------------------
        tags = wb_entry.get("tags", [])
        tag_text = "\n".join(
            f"- {t.get('zh', t.get('en', ''))}" for t in tags
        ) if tags else ""
        identity_content = f"""\
---
summary: "{expert_id} 的身份定义与能力边界"
---

## 身份

{display_name.get('zh', expert_id)} / {display_name.get('en', expert_id)}

## 专长标签

{tag_text or "(无特定标签)"}

## 能力边界

本专家定义由 WorkBuddy 导出，转换自 plugin: {wb_entry.get('plugin', 'N/A')}
agentName: {wb_entry.get('agentName', 'N/A')}
"""

        # ----------------------------------------------------------------
        # 7. Build USER.md (basic placeholder)
        # ----------------------------------------------------------------
        user_content = f"""\
---
summary: "{expert_id} 的用户画像假设"
---

## 目标用户

本专家适配以下场景的用户：
{wb_entry.get('description', {}).get('zh', '') or '(见 description)'}
"""

        # ----------------------------------------------------------------
        # 8. Build HEARTBEAT.md
        # ----------------------------------------------------------------
        default_prompt = wb_entry.get("defaultInitPrompt", {})
        if isinstance(default_prompt, str):
            default_prompt = {"en": default_prompt, "zh": default_prompt}
        heartbeat_body = default_prompt.get("zh", "") or default_prompt.get("en", "") or ""
        heartbeat_content = HEARTBEAT_TEMPLATE.format(heartbeat_body=heartbeat_body)

        # ----------------------------------------------------------------
        # 9. Copy avatar if it exists
        # ----------------------------------------------------------------
        dst_avatar: Path | None = None
        avatar_exts = [".png", ".jpg", ".jpeg", ".webp"]
        for ext in avatar_exts:
            src_avatar = self._avatars_root / f"{expert_id}{ext}"
            if src_avatar.exists():
                dst_avatar = dst_dir / f"avatar{ext}"
                if not self.dry_run:
                    dst_dir.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(src_avatar, dst_avatar)
                break

        # ----------------------------------------------------------------
        # 10. Write files (unless dry_run)
        # ----------------------------------------------------------------
        if not self.dry_run:
            dst_dir.mkdir(parents=True, exist_ok=True)
            with open(dst_manifest, "w", encoding="utf-8") as f:
                json.dump(octop_manifest, f, ensure_ascii=False, indent=2)
                f.write("\n")
            with open(dst_soul, "w", encoding="utf-8") as f:
                f.write(soul_content)
            with open(dst_identity, "w", encoding="utf-8") as f:
                f.write(identity_content)
            with open(dst_user, "w", encoding="utf-8") as f:
                f.write(user_content)
            with open(dst_heartbeat, "w", encoding="utf-8") as f:
                f.write(heartbeat_content)

            # Team experts: materialize roster + member subagent prompts so
            # Octop's agents/*.md seeding and TeamAgentRuntime can load them.
            if kind == "team":
                try:
                    from .team.parser import parse_team_soul, write_team_artifacts

                    definition = parse_team_soul(
                        soul_content,
                        expert_id=expert_id,
                        source=str(dst_soul),
                    )
                    write_team_artifacts(dst_dir, definition)
                except Exception as exc:  # pragma: no cover - best-effort
                    # Conversion of the lead expert still succeeds; roster is optional.
                    import logging

                    logging.getLogger(__name__).warning(
                        "team artifacts for %s failed: %s", expert_id, exc
                    )

        return ExpertConvertResult(
            expert_id=expert_id,
            kind=kind,
            success=True,
            skipped=skipped,
            src_path=src_prompt,
            dst_path=dst_dir,
        )

    def batch_convert(
        self,
        *,
        filter_kind: str | None = None,
    ) -> ConvertReport:
        """
        Convert all experts in the WorkBuddy manifest.

        Parameters
        ----------
        filter_kind : str | None
            If set to "agent", "team", or "plugin", only convert entries of that
            expertType. None (default) converts all.

        Returns
        -------
        ConvertReport
        """
        report = ConvertReport()

        manifest = self.load_wb_manifest()
        experts = manifest.get("experts", [])
        for entry in experts:
            kind = entry.get("expertType", "agent")
            if filter_kind and kind != filter_kind:
                continue
            result = self.convert_expert(entry)
            report.add(result)

        report.finish()
        return report
