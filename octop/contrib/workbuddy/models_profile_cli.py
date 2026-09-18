# SPDX-License-Identifier: MIT
"""CLI for model profiles."""

from __future__ import annotations

import argparse
import json

from .models_profile import ModelProfile, ModelProfileStore


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="model_profile_cli")
    p.add_argument("--path", default="artifacts/models/profiles.json")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list")
    g = sub.add_parser("get")
    g.add_argument("profile_id")
    s = sub.add_parser("set")
    s.add_argument("--id", dest="profile_id", required=True)
    s.add_argument("--base-url", required=True)
    s.add_argument("--model", required=True)
    s.add_argument("--api-key-env", default="OPENAI_API_KEY")
    a = sub.add_parser("activate")
    a.add_argument("profile_id")
    sub.add_parser("active")
    args = p.parse_args(argv)
    store = ModelProfileStore(args.path)

    if args.cmd == "list":
        print(json.dumps([x.to_dict() for x in store.list()], ensure_ascii=False, indent=2))
        return 0
    if args.cmd == "get":
        print(json.dumps(store.get(args.profile_id).to_dict(), ensure_ascii=False, indent=2))
        return 0
    if args.cmd == "set":
        prof = ModelProfile(
            profile_id=args.profile_id,
            base_url=args.base_url,
            model=args.model,
            api_key_env=args.api_key_env,
        )
        store.upsert(prof)
        print(json.dumps(prof.to_dict(), ensure_ascii=False, indent=2))
        return 0
    if args.cmd == "activate":
        print(json.dumps(store.set_active(args.profile_id).to_dict(), ensure_ascii=False, indent=2))
        return 0
    if args.cmd == "active":
        act = store.active()
        print(json.dumps(act.to_dict() if act else None, ensure_ascii=False, indent=2))
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
