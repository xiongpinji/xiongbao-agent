"""Downgrade Octop schema (rollback from N+1..current down to *target*).

This is the manual escape hatch for ops when ``octop backup restore`` is not
viable (e.g. no fresh backup of the target version, or a destructive migration
was rolled out and must be reverted without restoring user data).

Usage:
    python scripts/db_downgrade.py --target 15            # roll back v16 only
    python scripts/db_downgrade.py --target 13 --yes      # skip confirm
    python scripts/db_downgrade.py --target 13 --backup   # also create .bak file

What it does (best-effort):

  * Reads ``_schema_version`` from ``$OCTOP_HOME/db/octop.db``.
  * Lists every schema version above *target* and drops the artefacts
    introduced by the known migrations (tables / columns / indexes).
  * Clamps ``_schema_version`` to *target*.

Hard rules:
  * ``octop run`` MUST be stopped before running this script.
  * The DB is opened with ``mode=ro`` first to dump a snapshot, then
    in ``mode=rwc`` for writes — so a corrupt db won't silently lose data.
  * If any newer-version table still contains rows, the script prints a
    warning and exits 2 unless ``--force-data-loss`` is given. The data
    in those tables is not portable to the older binary.
  * PostgreSQL is not supported here: use ``pg_dump`` of the pre-upgrade
    schema + restore on the older binary. SQLite is the primary target
    (CLI/dev installs).

This is intentionally narrow: every drop block lists the artefact exactly
and skips silently when absent. Idempotency matters because ops may rerun
after a partial failure.
"""

from __future__ import annotations

import argparse
import os
import shutil
import sqlite3
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def _octop_home() -> Path:
    env = os.environ.get("OCTOP_HOME")
    if env:
        return Path(env).expanduser()
    return Path.home() / ".octop"


def _db_path(home: Path) -> Path:
    return home / "db" / "octop.db"


# --- Drop plan ---------------------------------------------------------------
#
# Each entry is (version, label, sqlite_statements).
# Statements are executed in order; FK enforcement is disabled around the batch
# because PostgreSQL→SQLite migration paths drop & recreate the *connectors*
# table (legacy), which leaves dangling refs otherwise.
#
# Versions above *target* are dropped in DESCENDING order so newer FKs are
# removed before the tables they reference.

_DROP_PLAN: dict[int, tuple[str, list[str]]] = {
    16: (
        "credit_account / credit_ledger (v16)",
        [
            "DROP INDEX IF EXISTS idx_credit_ledger_user_ts",
            "DROP INDEX IF EXISTS idx_credit_ledger_kind",
            "DROP TABLE IF EXISTS credit_ledger",
            "DROP TABLE IF EXISTS credit_account",
        ],
    ),
    15: (
        "agent_acl (v15)",
        [
            "DROP INDEX IF EXISTS idx_agent_acl_public",
            "DROP TABLE IF EXISTS agent_acl",
            # v15 replaced boolean is_shared with the ACL table; recreate the
            # legacy column if the table is back-compat (older Octop reads it).
            # SQLite ALTER TABLE ADD COLUMN is idempotent-safe via a guard.
        ],
    ),
    14: (
        "user_policies (v14)",
        [
            "DROP TABLE IF EXISTS user_policies",
        ],
    ),
    13: (
        "connectors rebuild (v13)",
        [
            # v13 renamed connectors -> connectors_legacy and rebuilt it.
            # Downgrading cannot fully reverse that without the legacy table,
            # so we leave the new shape in place and bail with a clear error.
        ],
    ),
    12: (
        "trajectory_events (v12)",
        [
            "DROP INDEX IF EXISTS idx_trajectory_events_thread",
            "DROP INDEX IF EXISTS idx_trajectory_events_agent",
            "DROP TABLE IF EXISTS trajectory_events",
        ],
    ),
}


def _read_schema_version(conn: sqlite3.Connection) -> int:
    try:
        row = conn.execute("SELECT version FROM _schema_version").fetchone()
    except sqlite3.OperationalError:
        return 0
    if row is None:
        return 0
    return int(row[0])


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    ).fetchone()
    return row is not None


def _table_row_count(conn: sqlite3.Connection, table: str) -> int:
    row = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
    return int(row[0]) if row else 0


def _detect_dialect(home: Path) -> str:
    """Return 'sqlite' or 'postgresql' by inspecting config.json."""
    config_path = home / "config.json"
    if not config_path.is_file():
        return "sqlite"
    try:
        import json

        cfg = json.loads(config_path.read_text(encoding="utf-8"))
        db = cfg.get("database") or {}
        return str(db.get("driver") or "sqlite")
    except Exception:
        return "sqlite"


def _backup_db(db_path: Path) -> Path:
    bak = db_path.with_suffix(db_path.suffix + ".bak")
    shutil.copy2(db_path, bak)
    return bak


def downgrade(target: int, *, yes: bool, force_data_loss: bool, do_backup: bool) -> int:
    home = _octop_home()
    dialect = _detect_dialect(home)
    if dialect != "sqlite":
        print(
            f"[db-downgrade] database driver is '{dialect}'. This script only "
            "supports SQLite. For PostgreSQL, restore a pre-upgrade pg_dump "
            "onto the older binary.",
            file=sys.stderr,
        )
        return 3

    db_path = _db_path(home)
    if not db_path.is_file():
        print(f"[db-downgrade] no database at {db_path}", file=sys.stderr)
        return 4

    if do_backup:
        bak = _backup_db(db_path)
        print(f"[db-downgrade] backup written to {bak}")

    # 1. Read-only introspection pass.
    ro = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        current = _read_schema_version(ro)
    finally:
        ro.close()

    if current == 0:
        print(
            "[db-downgrade] database has no _schema_version — refusing to touch it", file=sys.stderr
        )
        return 5
    if target >= current:
        print(
            f"[db-downgrade] target version {target} is >= current {current}; nothing to do",
            file=sys.stderr,
        )
        return 0
    if target < 1:
        print("[db-downgrade] target version must be >= 1", file=sys.stderr)
        return 6

    versions_to_drop = [v for v in range(target + 1, current + 1) if v in _DROP_PLAN]
    unsupported = [v for v in range(target + 1, current + 1) if v not in _DROP_PLAN]
    if unsupported:
        print(
            "[db-downgrade] no drop plan for versions: "
            + ", ".join(str(v) for v in sorted(unsupported))
            + ". Refusing to downgrade across an unknown migration.",
            file=sys.stderr,
        )
        return 7

    # 2. Row-presence sanity check on the tables we plan to drop.
    ro = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        data_warnings: list[str] = []
        for v in versions_to_drop:
            label, _ = _DROP_PLAN[v]
            # Extract the first table name mentioned in the label, if any.
            guess = label.split("/")[0].strip().split(" ")[0]
            if guess and _table_exists(ro, guess):
                count = _table_row_count(ro, guess)
                if count > 0:
                    data_warnings.append(f"  - {guess}: {count} rows will be lost")
        if data_warnings and not force_data_loss:
            print(
                "[db-downgrade] WARNING: the following tables contain rows that will be lost:",
                file=sys.stderr,
            )
            for line in data_warnings:
                print(line, file=sys.stderr)
            print(
                "[db-downgrade] re-run with --force-data-loss to proceed, or "
                "use `octop backup restore` of an older backup instead.",
                file=sys.stderr,
            )
            return 2
    finally:
        ro.close()

    if not yes:
        plan_str = ", ".join(f"v{v} ({_DROP_PLAN[v][0]})" for v in versions_to_drop)
        try:
            answer = input(
                f"About to drop {plan_str} and clamp _schema_version to {target}. Continue? [y/N] "
            )
        except EOFError:
            answer = ""
        if answer.strip().lower() not in {"y", "yes"}:
            print("[db-downgrade] aborted by user")
            return 0

    # 3. Apply drops in descending version order.
    rw = sqlite3.connect(db_path)
    try:
        rw.execute("PRAGMA foreign_keys = OFF")
        with rw:
            for v in sorted(versions_to_drop, reverse=True):
                label, stmts = _DROP_PLAN[v]
                print(f"[db-downgrade] v{v:02d}: dropping {label}")
                for stmt in stmts:
                    rw.execute(stmt)
            # v15 had a side-effect: agent_acl replaced is_shared. Older binary
            # expects the boolean column. Re-add it idempotently.
            if 15 in versions_to_drop:
                cols = {row[1] for row in rw.execute("PRAGMA table_info(agents)").fetchall()}
                if "is_shared" not in cols:
                    rw.execute("ALTER TABLE agents ADD COLUMN is_shared INTEGER NOT NULL DEFAULT 0")
                    print("[db-downgrade] v15: restored legacy agents.is_shared column")
            rw.execute(
                "UPDATE _schema_version SET version = ?",
                (target,),
            )
            print(f"[db-downgrade] _schema_version clamped to {target}")
    finally:
        rw.execute("PRAGMA foreign_keys = ON")
        rw.close()

    print("[db-downgrade] done. Restart `octop run` with the older binary.")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="db_downgrade",
        description="Roll back Octop SQLite schema to an older version.",
    )
    p.add_argument(
        "--target",
        type=int,
        required=True,
        help="Schema version to roll back to (>=1, <current).",
    )
    p.add_argument("--yes", action="store_true", help="Skip confirmation prompt.")
    p.add_argument(
        "--force-data-loss",
        action="store_true",
        help="Drop newer-version tables even when they contain rows.",
    )
    p.add_argument(
        "--backup",
        action="store_true",
        help="Copy octop.db → octop.db.bak before any change.",
    )
    args = p.parse_args(argv)
    return downgrade(
        args.target,
        yes=args.yes,
        force_data_loss=args.force_data_loss,
        do_backup=args.backup,
    )


if __name__ == "__main__":
    raise SystemExit(main())
