# SPDX-License-Identifier: MIT
"""Tests for Team parser + TeamAgentRuntime (no pytest required)."""

from __future__ import annotations

import asyncio
import sys
import tempfile
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT))

from octop.contrib.workbuddy.team.models import TeamDefinition  # noqa: E402
from octop.contrib.workbuddy.team.parser import (  # noqa: E402
    parse_team_soul,
    write_team_artifacts,
)
from octop.contrib.workbuddy.team.runtime import (  # noqa: E402
    MockMemberCaller,
    TeamAgentRuntime,
)

LIBRARY = (
    PROJECT
    / "octop"
    / "src"
    / "octop"
    / "infra"
    / "agents"
    / "experts"
    / "library"
)

passed: list[str] = []
failed: list[tuple[str, str]] = []


def test(name: str, fn) -> None:
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


STOCK_SOUL = """\
---
name: stock-partner-lead
description: orchestrator
---

# 投研专家团 - 主理人
## 圆汇众（Yuan） · 投研主编

## 团队成员

| 标记 | Agent 名称 | 花名 | 头衔 | 独特增量区 |
|------|-----------|------|------|-----------|
| 🌊 | `industry-strategist` | 星望远 | 产业策略师 | 产业趋势、产业链拆解 |
| 📡 | `signal-chief` | 洲四方 | 信号派首席 | 系统性风险预警 |
| 🧮 | `valuation-analyst` | 文衡价 | 估值分析师 | 估值定价 |
| 🏔️ | `contrarian-investor` | 坤候底 | 逆向投资人 | 逆向抄底 |
| 🔬 | `fundamental-researcher` | 钊审财 | 财报研究员 | 个股基本面 |
| ⚡ | `shortterm-surfer` | 磊追浪 | 短线冲浪手 | 短线主线 |

## 其他

不要解析这里的 `westock-data`。
"""

TRADING_SOUL = """\
---
name: trading-team-lead
---

# 交易分析团队 - 主理人

## 团队成员

| 成员 | Agent ID | 擅长领域 | 典型问法 | 所属阶段 |
|------|----------|---------|---------|----------|
| 技术分析师 | `market-analyst` | 价格走势 | "K线" | Phase 1 并行 |
| 基本面分析师 | `fundamentals-analyst` | 财报 | "估值" | Phase 1 并行 |
| 多头研究员 | `bull-researcher` | 看多 | "为什么买" | Phase 2 顺序 |
| 空头研究员 | `bear-researcher` | 看空 | "风险" | Phase 2 顺序 |
| 交易员 | `trader` | 交易提案 | "怎么做" | Phase 3 |
| 风险主管 | `risk-manager` | 最终决策 | "买不买" | Phase 4 顺序 |
"""


def t_parse_stock_roundtable():
    d = parse_team_soul(STOCK_SOUL, expert_id="StockPartnerTeam")
    assert d.lead_id == "stock-partner-lead", d.lead_id
    assert len(d.members) == 6, [m.agent_id for m in d.members]
    assert d.orchestration == "roundtable", d.orchestration
    assert len(d.phases) == 1
    assert d.phases[0].mode == "parallel"
    ids = {m.agent_id for m in d.members}
    assert "industry-strategist" in ids
    assert "shortterm-surfer" in ids
    assert "westock-data" not in ids


def t_parse_trading_phased():
    d = parse_team_soul(TRADING_SOUL, expert_id="TradingAgentTeam")
    assert d.lead_id == "trading-team-lead"
    assert len(d.members) == 6, [m.agent_id for m in d.members]
    assert d.orchestration == "phased", d.orchestration
    assert len(d.phases) >= 3, [p.id for p in d.phases]
    p1 = next(p for p in d.phases if p.id == "phase-1")
    assert p1.mode == "parallel"
    assert set(p1.member_ids) == {"market-analyst", "fundamentals-analyst"}
    p2 = next(p for p in d.phases if p.id == "phase-2")
    assert p2.mode == "sequential"


def t_write_artifacts():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "StockPartnerTeam"
        root.mkdir()
        (root / "SOUL.md").write_text(STOCK_SOUL, encoding="utf-8")
        d = parse_team_soul(STOCK_SOUL, expert_id="StockPartnerTeam", source=str(root / "SOUL.md"))
        write_team_artifacts(root, d)
        assert (root / "team.json").is_file()
        assert (root / "agents" / "industry-strategist.md").is_file()
        text = (root / "agents" / "industry-strategist.md").read_text(encoding="utf-8")
        assert "产业策略师" in text
        reloaded = TeamDefinition.from_dict(
            __import__("json").loads((root / "team.json").read_text(encoding="utf-8"))
        )
        assert len(reloaded.members) == 6


def t_runtime_dry_run():
    d = parse_team_soul(STOCK_SOUL, expert_id="StockPartnerTeam")
    rt = TeamAgentRuntime(d)
    result = rt.run_sync("帮我分析茅台", dry_run=True)
    assert result.dry_run is True
    assert len(result.plan) >= 3
    assert result.plan[0]["step"] == "create_team"
    assert any(s["step"] == "dispatch_phase" for s in result.plan)
    assert result.plan[-1]["step"] == "synthesize"


def t_runtime_mock_live():
    d = parse_team_soul(STOCK_SOUL, expert_id="StockPartnerTeam")
    rt = TeamAgentRuntime(d, caller=MockMemberCaller())
    result = asyncio.run(rt.run("帮我分析茅台该不该买"))
    assert result.dry_run is False
    assert len(result.member_outputs) == 6, len(result.member_outputs)
    assert "圆桌综合报告" in result.final_report or "综合" in result.final_report
    assert all(o.content for o in result.member_outputs)


def t_runtime_trading_phase_order():
    d = parse_team_soul(TRADING_SOUL, expert_id="TradingAgentTeam")
    rt = TeamAgentRuntime(d, caller=MockMemberCaller())
    result = asyncio.run(rt.run("分析宁德时代"))
    assert len(result.member_outputs) == 6
    # Phase order preserved: phase-1 members before phase-2
    phases = [o.phase_id for o in result.member_outputs]
    assert phases.index("phase-1") < phases.index("phase-2")
    assert phases.index("phase-2") < phases.index("phase-3")


def t_library_stock_partner():
    path = LIBRARY / "StockPartnerTeam" / "SOUL.md"
    if not path.is_file():
        print("  [skip] library StockPartnerTeam not present")
        return
    d = parse_team_soul(path.read_text(encoding="utf-8"), expert_id="StockPartnerTeam")
    assert d.lead_id == "stock-partner-lead", d.lead_id
    assert len(d.members) >= 5, [m.agent_id for m in d.members]
    assert "industry-strategist" in {m.agent_id for m in d.members}


def t_library_trading():
    path = LIBRARY / "TradingAgentTeam" / "SOUL.md"
    if not path.is_file():
        print("  [skip] library TradingAgentTeam not present")
        return
    d = parse_team_soul(path.read_text(encoding="utf-8"), expert_id="TradingAgentTeam")
    assert d.lead_id == "trading-team-lead"
    assert len(d.members) >= 8, [m.agent_id for m in d.members]


def t_parse_plain_id_and_md_suffix():
    soul = """\
---
name: software-team-lead
---
# Lead

## 团队成员

| 角色 | Prompt | 职责 |
|------|--------|------|
| 产品经理 | `software-product-manager.md` | 写 PRD |
| 架构师 | `software-architect.md` | 设计架构 |
"""
    d = parse_team_soul(soul, expert_id="SoftwareCompany")
    assert {m.agent_id for m in d.members} == {
        "software-product-manager",
        "software-architect",
    }


def t_parse_plain_first_column():
    soul = """\
---
name: chatlaw-team-lead
---
## 团队成员

| 成员 | 名字 | 职责 |
|------|------|------|
| info-intake | 方助理 | 采集案情 |
| legal-research | 周法官 | 检索法条 |
"""
    d = parse_team_soul(soul, expert_id="ChatLawTeam")
    assert len(d.members) == 2
    assert d.members[0].agent_id == "info-intake"
    assert "方助理" in d.members[0].display_name


def t_parse_heading_cards():
    soul = """\
---
name: a-share-advisor
---
## 团队成员

### 🌐 宏观策略师 `macro-strategist`
职责说明

### 🔬 个股研究员 `stock-researcher`
职责说明
"""
    d = parse_team_soul(soul, expert_id="AShareAnalysis")
    assert {m.agent_id for m in d.members} == {"macro-strategist", "stock-researcher"}


test("parse_stock_roundtable", t_parse_stock_roundtable)
test("parse_trading_phased", t_parse_trading_phased)
test("parse_plain_id_and_md_suffix", t_parse_plain_id_and_md_suffix)
test("parse_plain_first_column", t_parse_plain_first_column)
test("parse_heading_cards", t_parse_heading_cards)
test("write_artifacts", t_write_artifacts)
test("runtime_dry_run", t_runtime_dry_run)
test("runtime_mock_live", t_runtime_mock_live)
test("runtime_trading_phase_order", t_runtime_trading_phase_order)
test("library_stock_partner", t_library_stock_partner)
test("library_trading", t_library_trading)

print(f"\n=== {len(passed)} passed, {len(failed)} failed ===")
if failed:
    for n, e in failed:
        print(f"  - {n}: {e}")
    sys.exit(1)
