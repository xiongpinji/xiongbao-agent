# SPDX-License-Identifier: MIT
"""CLI: multi-tenant registry, auth, quota, backup."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .tenant import (
    TenantQuota,
    TenantRegistry,
    TenantRoots,
    backup_tenant,
    issue_token,
    restore_tenant,
    tenant_collection,
    usage_snapshot,
)


def _print(obj: object) -> None:
    print(json.dumps(obj, ensure_ascii=False, indent=2))


def cmd_create(args: argparse.Namespace) -> int:
    reg = TenantRegistry(args.registry)
    rec, api_key = reg.create(
        args.tenant_id,
        name=args.name or "",
        admin_user_id=args.admin,
    )
    _print(
        {
            "ok": True,
            "tenant": rec.to_dict(),
            "admin_user_id": args.admin,
            "admin_api_key": api_key,
            "roots": TenantRoots(rec.tenant_id, args.admin).to_dict(),
            "hint": "Store admin_api_key securely; it is shown once.",
        }
    )
    return 0


def cmd_add_user(args: argparse.Namespace) -> int:
    reg = TenantRegistry(args.registry)
    user, api_key = reg.add_user(
        args.tenant_id,
        args.user_id,
        role=args.role,
        display_name=args.name or "",
    )
    _print(
        {
            "ok": True,
            "user": user.to_dict(),
            "api_key": api_key,
            "roots": TenantRoots(args.tenant_id, args.user_id).to_dict(),
        }
    )
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    reg = TenantRegistry(args.registry)
    _print({"ok": True, "tenants": [t.to_dict() for t in reg.list_tenants()]})
    return 0


def cmd_login(args: argparse.Namespace) -> int:
    reg = TenantRegistry(args.registry)
    ctx = reg.authenticate(args.tenant_id, args.user_id, args.api_key)
    token = issue_token(ctx, ttl_sec=int(args.ttl))
    _print({"ok": True, "token": token, "claims": ctx.to_claims()})
    return 0


def cmd_roots(args: argparse.Namespace) -> int:
    roots = TenantRoots(args.tenant_id, args.user_id)
    roots.ensure()
    _print({"ok": True, **roots.to_dict()})
    return 0


def cmd_quota(args: argparse.Namespace) -> int:
    reg = TenantRegistry(args.registry)
    if args.set:
        q = TenantQuota(
            max_users=int(args.max_users),
            max_tasks=int(args.max_tasks),
            max_storage_mb=int(args.max_storage_mb),
            max_agents=int(args.max_agents),
        )
        rec = reg.set_quota(args.tenant_id, q)
        _print({"ok": True, "quota": rec.quota.to_dict()})
        return 0
    rec = reg.get(args.tenant_id)
    if rec is None:
        print(json.dumps({"ok": False, "error": "not found"}), file=sys.stderr)
        return 1
    uid = args.user_id or (rec.users[0].user_id if rec.users else "admin")
    _print({"ok": True, **usage_snapshot(rec, uid)})
    return 0


def cmd_backup(args: argparse.Namespace) -> int:
    out = args.out or f"artifacts/backups/{args.tenant_id}-{Path.cwd().name}.zip"
    result = backup_tenant(args.tenant_id, out, registry=TenantRegistry(args.registry))
    _print(result)
    return 0


def cmd_restore(args: argparse.Namespace) -> int:
    result = restore_tenant(
        args.archive,
        registry=TenantRegistry(args.registry),
        overwrite=bool(args.overwrite),
    )
    _print(result)
    return 0


def cmd_milvus(args: argparse.Namespace) -> int:
    _print({"ok": True, "collection": tenant_collection(args.tenant_id)})
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="tenant_cli", description="WorkBuddy multi-tenant ops")
    p.add_argument("--registry", default="artifacts/tenants/_registry.json")
    sub = p.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("create", help="Create tenant + admin")
    c.add_argument("tenant_id")
    c.add_argument("--name", default="")
    c.add_argument("--admin", default="admin")
    c.set_defaults(func=cmd_create)

    a = sub.add_parser("add-user", help="Add user to tenant")
    a.add_argument("tenant_id")
    a.add_argument("user_id")
    a.add_argument("--role", default="user")
    a.add_argument("--name", default="")
    a.set_defaults(func=cmd_add_user)

    l = sub.add_parser("list", help="List tenants")
    l.set_defaults(func=cmd_list)

    login = sub.add_parser("login", help="Exchange api_key → JWT")
    login.add_argument("tenant_id")
    login.add_argument("user_id")
    login.add_argument("api_key")
    login.add_argument("--ttl", type=int, default=7200)
    login.set_defaults(func=cmd_login)

    r = sub.add_parser("roots", help="Show/ensure tenant roots")
    r.add_argument("tenant_id")
    r.add_argument("user_id")
    r.set_defaults(func=cmd_roots)

    q = sub.add_parser("quota", help="Show or set quota")
    q.add_argument("tenant_id")
    q.add_argument("--user-id", default="")
    q.add_argument("--set", action="store_true")
    q.add_argument("--max-users", type=int, default=50)
    q.add_argument("--max-tasks", type=int, default=500)
    q.add_argument("--max-storage-mb", type=int, default=1024)
    q.add_argument("--max-agents", type=int, default=20)
    q.set_defaults(func=cmd_quota)

    b = sub.add_parser("backup", help="Backup tenant slice")
    b.add_argument("tenant_id")
    b.add_argument("--out", default="")
    b.set_defaults(func=cmd_backup)

    rs = sub.add_parser("restore", help="Restore tenant slice")
    rs.add_argument("archive")
    rs.add_argument("--overwrite", action="store_true")
    rs.set_defaults(func=cmd_restore)

    m = sub.add_parser("milvus-ns", help="Print Milvus collection for tenant")
    m.add_argument("tenant_id")
    m.set_defaults(func=cmd_milvus)

    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return int(args.func(args))
    except Exception as exc:  # noqa: BLE001 — CLI boundary
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
