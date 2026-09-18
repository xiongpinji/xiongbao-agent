# SPDX-License-Identifier: MIT
"""CLI: library / inspiration / knowledge / cowrite / channel bridge."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .channel_bridge import ChannelBridge
from .cowrite import CowriteStore
from .inspiration import InspirationCatalog
from .knowledge import LocalKnowledgeBase
from .library import LibraryIndex
from .task import TaskStore


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="parity_cli", description="V9 parity surfaces")
    sub = p.add_subparsers(dest="cmd", required=True)

    # library
    lib = sub.add_parser("library")
    lib_sub = lib.add_subparsers(dest="lib_cmd", required=True)
    la = lib_sub.add_parser("add")
    la.add_argument("--root", default="artifacts/library")
    la.add_argument("--file", required=True)
    la.add_argument("--title", default="")
    ll = lib_sub.add_parser("list")
    ll.add_argument("--root", default="artifacts/library")
    lp = lib_sub.add_parser("publish")
    lp.add_argument("--root", default="artifacts/library")
    lp.add_argument("--title", default="WorkBuddy Library")

    # inspiration
    insp = sub.add_parser("inspiration")
    insp_sub = insp.add_subparsers(dest="insp_cmd", required=True)
    insp_sub.add_parser("list")
    isc = insp_sub.add_parser("scaffold")
    isc.add_argument("--id", required=True)
    isc.add_argument("--dest", required=True)

    # knowledge
    kb = sub.add_parser("knowledge")
    kb_sub = kb.add_subparsers(dest="kb_cmd", required=True)
    ki = kb_sub.add_parser("ingest")
    ki.add_argument("--root", default="artifacts/knowledge")
    ki.add_argument("--file", required=True)
    ks = kb_sub.add_parser("search")
    ks.add_argument("--root", default="artifacts/knowledge")
    ks.add_argument("--query", required=True)
    ks.add_argument("--limit", type=int, default=5)
    km = kb_sub.add_parser("milvus-dry")
    km.add_argument("--root", default="artifacts/knowledge")

    # cowrite
    cw = sub.add_parser("cowrite")
    cw_sub = cw.add_subparsers(dest="cw_cmd", required=True)
    cws = cw_sub.add_parser("start")
    cws.add_argument("--root", default="artifacts/cowrite")
    cws.add_argument("--title", required=True)
    cws.add_argument("--seed", default="")
    cwa = cw_sub.add_parser("append")
    cwa.add_argument("--root", default="artifacts/cowrite")
    cwa.add_argument("--id", required=True)
    cwa.add_argument("--author", default="human", choices=["human", "assistant"])
    cwa.add_argument("--text", required=True)
    cwe = cw_sub.add_parser("export")
    cwe.add_argument("--root", default="artifacts/cowrite")
    cwe.add_argument("--id", required=True)
    cwe.add_argument("--out", required=True)

    # bridge
    br = sub.add_parser("bridge")
    br.add_argument("--tasks-root", default="artifacts/tasks")
    br.add_argument("--provider", default="wechat")
    br.add_argument("--text", required=True)
    br.add_argument("--allow", action="store_true")

    args = p.parse_args(argv)

    if args.cmd == "library":
        idx = LibraryIndex(args.root)
        if args.lib_cmd == "add":
            e = idx.add_file(args.file, title=args.title)
            print(json.dumps(e.to_dict(), ensure_ascii=False, indent=2))
            return 0
        if args.lib_cmd == "list":
            print(json.dumps([e.to_dict() for e in idx.list_entries()], ensure_ascii=False, indent=2))
            return 0
        if args.lib_cmd == "publish":
            out = idx.publish(site_title=args.title)
            print(json.dumps({"published": str(out)}, indent=2))
            return 0

    if args.cmd == "inspiration":
        cat = InspirationCatalog()
        if args.insp_cmd == "list":
            print(json.dumps(cat.list(), ensure_ascii=False, indent=2))
            return 0
        if args.insp_cmd == "scaffold":
            dest = cat.scaffold(args.id, args.dest)
            print(json.dumps({"dest": str(dest)}, indent=2))
            return 0

    if args.cmd == "knowledge":
        kb_store = LocalKnowledgeBase(args.root)
        if args.kb_cmd == "ingest":
            chunks = kb_store.ingest_file(args.file)
            print(json.dumps({"chunks": len(chunks)}, indent=2))
            return 0
        if args.kb_cmd == "search":
            print(json.dumps(kb_store.search(args.query, limit=args.limit), ensure_ascii=False, indent=2))
            return 0
        if args.kb_cmd == "milvus-dry":
            print(json.dumps(kb_store.upsert_milvus_dry(), indent=2))
            return 0

    if args.cmd == "cowrite":
        store = CowriteStore(args.root)
        if args.cw_cmd == "start":
            s = store.start(args.title, seed=args.seed)
            print(json.dumps(s.to_dict(), ensure_ascii=False, indent=2))
            return 0
        if args.cw_cmd == "append":
            s = store.append(args.id, args.author, args.text)
            print(json.dumps({"session_id": s.session_id, "turns": len(s.turns)}, indent=2))
            return 0
        if args.cw_cmd == "export":
            out = store.export_markdown(args.id, args.out)
            print(json.dumps({"wrote": str(out)}, indent=2))
            return 0

    if args.cmd == "bridge":
        bridge = ChannelBridge(TaskStore(args.tasks_root), allow=bool(args.allow))
        result = bridge.handle_inbound(args.provider, args.text)
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
        return 0 if result.ok else 1

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
