"""在 Octop DB 里直接注册 deepseek provider。Phase A.3 工具脚本。

不通过 `octop provider create` CLI（PowerShell 解析多层 JSON 太麻烦），直接用
SQLite + repo 创建。完成后输出 provider_id 和下一步指令。
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(os.environ.get("OCTOP_HOME", Path.home() / ".octop"))
DB_PATH = ROOT / "octop.db"
KEY_NAME = "deepseek"
API_KEY = "sk-3a60eea2d0104fb69217ffbe64ff19fc"
BASE_URL = "https://api.deepseek.com/v1"
MODELS = [{"id": "deepseek-chat", "label": "DeepSeek Chat"}]


def main() -> int:
    if not DB_PATH.exists():
        print(f"DB not found at {DB_PATH}", file=sys.stderr)
        return 1
    # Read existing providers
    import sqlite3
    con = sqlite3.connect(str(DB_PATH))
    con.row_factory = sqlite3.Row
    try:
        row = con.execute(
            "SELECT id, name, kind, base_url, models_json, enabled FROM providers WHERE name = ?",
            (KEY_NAME,),
        ).fetchone()
        if row:
            print(f"provider already exists: id={row['id']} name={row['name']} kind={row['kind']}")
            con.execute(
                "UPDATE providers SET base_url = ?, api_key = ?, models_json = ?, enabled = 1, updated_at = ? WHERE id = ?",
                (BASE_URL, API_KEY, json.dumps(MODELS), int(__import__("time").time()), row["id"]),
            )
            con.commit()
            print("updated base_url + api_key + models")
        else:
            now = int(__import__("time").time())
            cur = con.execute(
                """
                INSERT INTO providers (name, kind, base_url, api_key, models_json, enabled, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, 1, ?, ?)
                """,
                (KEY_NAME, "openai_compatible", BASE_URL, API_KEY, json.dumps(MODELS), now, now),
            )
            con.commit()
            print(f"created provider id={cur.lastrowid} name={KEY_NAME}")
        # verify
        rows = con.execute(
            "SELECT id, name, kind, base_url, models_json, enabled FROM providers WHERE name = ?",
            (KEY_NAME,),
        ).fetchall()
        for r in rows:
            print(json.dumps({
                "id": r["id"],
                "name": r["name"],
                "kind": r["kind"],
                "base_url": r["base_url"],
                "models": json.loads(r["models_json"]) if r["models_json"] else [],
                "enabled": bool(r["enabled"]),
            }, ensure_ascii=False, indent=2))
    finally:
        con.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
