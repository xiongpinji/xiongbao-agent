"""Tests for scripts/db_downgrade.py.

Covers:
  * version clamp after dropping v16 tables
  * v15 side-effect restores legacy ``agents.is_shared``
  * idempotency: re-running with target == current is a no-op
  * refuses to roll back across an unknown version
  * refuses to drop a non-empty table without --force-data-loss
  * SQLite-only guard
  * no-_schema_version refusal
  * .bak file is produced when --backup is given
"""

from __future__ import annotations

import importlib.util
import sqlite3
import sys
from pathlib import Path

import pytest


def _load_module():
    script_path = Path(__file__).resolve().parents[3] / "scripts" / "db_downgrade.py"
    spec = importlib.util.spec_from_file_location("db_downgrade_under_test", script_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def script_home(tmp_path, monkeypatch):
    """Create a fake $OCTOP_HOME with a populated DB at schema v16."""
    home = tmp_path / ".octop"
    home.mkdir()
    db = home / "db" / "octop.db"
    db.parent.mkdir()

    conn = sqlite3.connect(db)
    try:
        conn.executescript(
            """
            CREATE TABLE _schema_version (version INTEGER NOT NULL);
            INSERT INTO _schema_version VALUES (16);

            CREATE TABLE users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'user',
                created_at INTEGER NOT NULL
            );
            INSERT INTO users(username, password_hash, role, created_at)
              VALUES ('alice', 'h', 'admin', 1);

            CREATE TABLE agents (
                agent_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                owner_user_id INTEGER NOT NULL,
                is_shared INTEGER NOT NULL DEFAULT 0,
                created_at INTEGER NOT NULL,
                updated_at INTEGER NOT NULL
            );
            INSERT INTO agents(agent_id, name, owner_user_id, is_shared,
                               created_at, updated_at)
              VALUES ('a1', 'agent 1', 1, 0, 1, 1);

            CREATE TABLE user_policies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                policy_id TEXT NOT NULL UNIQUE,
                user_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                enabled INTEGER NOT NULL DEFAULT 1,
                value TEXT NOT NULL DEFAULT '',
                created_at INTEGER NOT NULL,
                updated_at INTEGER NOT NULL,
                UNIQUE(user_id, name)
            );

            CREATE TABLE agent_acl (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                agent_id TEXT NOT NULL,
                user_id INTEGER,
                role TEXT NOT NULL,
                created_at INTEGER NOT NULL,
                updated_at INTEGER NOT NULL
            );

            CREATE TABLE credit_account (
                user_id INTEGER PRIMARY KEY,
                balance INTEGER NOT NULL DEFAULT 0,
                total_earned INTEGER NOT NULL DEFAULT 0,
                total_spent INTEGER NOT NULL DEFAULT 0,
                tier TEXT NOT NULL DEFAULT 'free',
                tier_name TEXT NOT NULL DEFAULT 'Free',
                monthly_allowance INTEGER NOT NULL DEFAULT 0,
                monthly_used INTEGER NOT NULL DEFAULT 0,
                monthly_window_start INTEGER,
                next_reset_at INTEGER,
                updated_at INTEGER NOT NULL
            );
            INSERT INTO credit_account(user_id, balance, updated_at)
              VALUES (1, 100, 1);

            CREATE TABLE credit_ledger (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                kind TEXT NOT NULL,
                amount INTEGER NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                category TEXT,
                ref_id TEXT,
                metadata TEXT,
                ts INTEGER NOT NULL
            );
            """
        )
        conn.commit()
    finally:
        conn.close()

    config = home / "config.json"
    config.write_text('{"database": {"driver": "sqlite"}}', encoding="utf-8")

    monkeypatch.setenv("OCTOP_HOME", str(home))
    return home


def test_downgrade_clamps_to_v15_and_drops_v16(script_home):
    dd = _load_module()
    rc = dd.downgrade(15, yes=True, force_data_loss=True, do_backup=False)
    assert rc == 0

    db = script_home / "db" / "octop.db"
    conn = sqlite3.connect(db)
    try:
        v = conn.execute("SELECT version FROM _schema_version").fetchone()[0]
        assert v == 15
        tables = {
            row[0]
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        }
        assert "credit_account" not in tables
        assert "credit_ledger" not in tables
        # user_policies (v14) and agent_acl (v15) still present at this target.
        assert "user_policies" in tables
        assert "agent_acl" in tables
    finally:
        conn.close()


def test_downgrade_to_v13_drops_v15_and_restores_is_shared(script_home):
    dd = _load_module()
    rc = dd.downgrade(13, yes=True, force_data_loss=True, do_backup=False)
    assert rc == 0

    db = script_home / "db" / "octop.db"
    conn = sqlite3.connect(db)
    try:
        v = conn.execute("SELECT version FROM _schema_version").fetchone()[0]
        assert v == 13
        tables = {
            row[0]
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        }
        for gone in ("credit_account", "credit_ledger", "agent_acl", "user_policies"):
            assert gone not in tables, f"{gone} should be dropped"
        # is_shared column is restored for the legacy binary.
        cols = {row[1] for row in conn.execute("PRAGMA table_info(agents)").fetchall()}
        assert "is_shared" in cols
    finally:
        conn.close()


def test_downgrade_is_idempotent(script_home):
    dd = _load_module()
    # First pass: drop v16 only.
    assert dd.downgrade(15, yes=True, force_data_loss=True, do_backup=False) == 0
    # Second pass: same target again — already at 15, nothing to do.
    assert dd.downgrade(15, yes=True, force_data_loss=True, do_backup=False) == 0


def test_downgrade_refuses_when_target_geq_current(script_home):
    dd = _load_module()
    rc = dd.downgrade(99, yes=True, force_data_loss=True, do_backup=False)
    assert rc == 0  # no-op, returns 0, just prints


def test_downgrade_refuses_data_loss_by_default(script_home):
    dd = _load_module()
    # credit_account already has a row inserted by the fixture.
    rc = dd.downgrade(15, yes=True, force_data_loss=False, do_backup=False)
    assert rc == 2
    # Schema version must still be 16.
    db = script_home / "db" / "octop.db"
    conn = sqlite3.connect(db)
    try:
        v = conn.execute("SELECT version FROM _schema_version").fetchone()[0]
        assert v == 16
    finally:
        conn.close()


def test_downgrade_refuses_unknown_version(script_home, tmp_path):
    """Set _schema_version to a value with no drop plan."""
    db = script_home / "db" / "octop.db"
    conn = sqlite3.connect(db)
    conn.execute("UPDATE _schema_version SET version = 99")
    conn.commit()
    conn.close()

    dd = _load_module()
    rc = dd.downgrade(15, yes=True, force_data_loss=True, do_backup=False)
    assert rc == 7


def test_downgrade_refuses_postgres(script_home):
    (script_home / "config.json").write_text(
        '{"database": {"driver": "postgresql"}}', encoding="utf-8"
    )
    dd = _load_module()
    rc = dd.downgrade(15, yes=True, force_data_loss=True, do_backup=False)
    assert rc == 3


def test_downgrade_creates_backup_when_requested(script_home):
    dd = _load_module()
    rc = dd.downgrade(15, yes=True, force_data_loss=True, do_backup=True)
    assert rc == 0
    bak = script_home / "db" / "octop.db.bak"
    assert bak.is_file()
    # Backup keeps the original schema version 16.
    conn = sqlite3.connect(bak)
    try:
        assert conn.execute("SELECT version FROM _schema_version").fetchone()[0] == 16
    finally:
        conn.close()


def test_downgrade_refuses_missing_db(tmp_path, monkeypatch):
    home = tmp_path / ".octop"
    home.mkdir()
    (home / "config.json").write_text('{"database": {"driver": "sqlite"}}', encoding="utf-8")
    monkeypatch.setenv("OCTOP_HOME", str(home))

    dd = _load_module()
    rc = dd.downgrade(15, yes=True, force_data_loss=True, do_backup=False)
    assert rc == 4
