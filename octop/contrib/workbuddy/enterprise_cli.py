# SPDX-License-Identifier: MIT
"""CLI: enterprise Casdoor / Milvus clients + probe."""

from __future__ import annotations

import argparse
import json
import sys

from .enterprise import casdoor, enterprise_probe, milvus


def cmd_probe(_args: argparse.Namespace) -> int:
    print(json.dumps(enterprise_probe(), ensure_ascii=False, indent=2))
    return 0


def cmd_casdoor_discovery(_args: argparse.Namespace) -> int:
    print(json.dumps(casdoor.fetch_oidc_discovery(), ensure_ascii=False, indent=2))
    return 0


def cmd_casdoor_verify(args: argparse.Namespace) -> int:
    try:
        result = casdoor.verify_access_token(args.token)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result.get("verified") or "payload" in result else 1
    except Exception as exc:  # noqa: BLE001
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False, indent=2))
        return 1


def cmd_milvus_status(_args: argparse.Namespace) -> int:
    print(json.dumps(milvus.rag_status(), ensure_ascii=False, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="enterprise_cli", description="Casdoor/Milvus enterprise")
    sub = p.add_subparsers(dest="cmd", required=True)
    pr = sub.add_parser("probe", help="Env + reachability + wired clients")
    pr.set_defaults(func=cmd_probe)
    cd = sub.add_parser("casdoor-discovery", help="Fetch OIDC discovery document")
    cd.set_defaults(func=cmd_casdoor_discovery)
    cv = sub.add_parser("casdoor-verify", help="Verify HS256 access token")
    cv.add_argument("--token", required=True)
    cv.set_defaults(func=cmd_casdoor_verify)
    ms = sub.add_parser("milvus-status", help="RAG / list collections status")
    ms.set_defaults(func=cmd_milvus_status)
    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
