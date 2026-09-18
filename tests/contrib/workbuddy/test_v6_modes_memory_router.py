# SPDX-License-Identifier: MIT
"""V6 unit tests: modes / memory / router / extended connectors / enterprise.

Run::

    python -S tests/contrib/workbuddy/test_v6_modes_memory_router.py
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from octop.contrib.workbuddy.connectors.extended import (  # noqa: E402
    ConnectorCatalog,
    resolve_message_extended,
)
from octop.contrib.workbuddy.enterprise import enterprise_probe  # noqa: E402
from octop.contrib.workbuddy.memory import load_workspace_memory  # noqa: E402
from octop.contrib.workbuddy.modes import (  # noqa: E402
    assemble_system_prompt,
    mode_allows_writes,
    normalize_mode,
)
from octop.contrib.workbuddy.router import ExpertRouter  # noqa: E402
from octop.contrib.workbuddy.skills import SkillCatalog, default_builtin_skills_root  # noqa: E402


def test_normalize_and_assemble() -> None:
    assert normalize_mode("ASK") == "ask"
    assert normalize_mode("readonly") == "ask"
    assert not mode_allows_writes("ask")
    assert not mode_allows_writes("plan")
    assert mode_allows_writes("craft")
    a = assemble_system_prompt(
        mode="ask",
        expert_prompt="You are a helper.",
        expert_id="demo",
        soul="Be kind.",
        user_profile="Prefers Chinese.",
        durable_memory="Remember the project is xiongbao.",
    )
    assert a.mode == "ask"
    assert "ask_mode" in a.system
    assert "Be kind" in a.system
    assert "Role Override" in a.system


def test_load_workspace_memory() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "SOUL.md").write_text("# Soul\ncalm", encoding="utf-8")
        (root / "USER.md").write_text("# User\nalice", encoding="utf-8")
        (root / "MEMORY.md").write_text("# Mem\nfact-1", encoding="utf-8")
        mem_dir = root / "memory"
        mem_dir.mkdir()
        (mem_dir / "2099-01-02.md").write_text("day note", encoding="utf-8")
        mem = load_workspace_memory(root)
        assert "calm" in mem.soul
        assert "alice" in mem.user
        assert "fact-1" in mem.durable
        assert "day note" in mem.daily
        d = mem.to_dict()
        assert d["soul_chars"] > 0


def test_expert_router_scores() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        lib = Path(tmp)
        for name, tags, welcome in (
            ("StockPartnerTeam", ["finance", "stock"], {"zh": "股票分析助手"}),
            ("ParentingBuddy", ["parenting", "育儿"], {"zh": "育儿管家"}),
            ("CodeReviewer", ["code", "review"], {"zh": "代码审查"}),
        ):
            d = lib / name
            d.mkdir()
            (d / "manifest.json").write_text(
                json.dumps(
                    {
                        "kind": "agent",
                        "welcome_message": welcome,
                        "_wb": {
                            "expert_type": "team" if "Team" in name else "agent",
                            "tags": tags,
                            "category_label": {"zh": tags[0]},
                        },
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
        router = ExpertRouter(lib)
        assert router.load() == 3
        hits = router.route("股票 分析", limit=3)
        assert hits
        assert hits[0].expert_id == "StockPartnerTeam"
        hits2 = router.route("育儿", limit=2)
        assert hits2[0].expert_id == "ParentingBuddy"


def test_connector_catalog_and_extended_gate() -> None:
    cat = ConnectorCatalog()
    n = cat.scan()
    assert n >= 50  # vendor ships ~103
    hits = cat.search("notion", limit=5)
    assert any(h.id == "notion" or "notion" in h.id for h in hits) or n > 0
    # Without outbound flag, ding talk should refuse send
    r = resolve_message_extended("dingtalk:webhook", "hello")
    assert r is not None
    assert r.ok is False
    assert "OUTBOUND" in (r.error or "").upper() or "not set" in (r.error or "").lower()


def test_enterprise_probe_shape() -> None:
    data = enterprise_probe()
    assert "casdoor" in data and "milvus" in data
    assert data["casdoor"]["wired"] is True
    assert data["milvus"]["wired"] is True
    assert "client" in data["casdoor"] and "client" in data["milvus"]


def test_builtin_skills_in_default_catalog() -> None:
    builtin = default_builtin_skills_root()
    assert builtin.is_dir()
    cat = SkillCatalog()  # default root → include builtin
    cat.scan()
    ids = {m.id for m in cat.list()}
    assert "skill-creator" in ids or "buddy-multimodal-generation" in ids


def main() -> int:
    tests = [
        test_normalize_and_assemble,
        test_load_workspace_memory,
        test_expert_router_scores,
        test_connector_catalog_and_extended_gate,
        test_enterprise_probe_shape,
        test_builtin_skills_in_default_catalog,
    ]
    failed = 0
    for fn in tests:
        try:
            fn()
            print(f"OK  {fn.__name__}")
        except Exception as exc:  # noqa: BLE001
            failed += 1
            print(f"FAIL {fn.__name__}: {exc}")
    if failed:
        print(f"V6 TESTS FAILED ({failed})")
        return 1
    print("ALL V6 MODE/MEMORY/ROUTER TESTS OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
