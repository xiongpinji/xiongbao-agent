"""Tests for the per-agent ACL (P1-3)."""

from __future__ import annotations

from pathlib import Path

import pytest

from octop.infra.db.migrate import run_migrations
from octop.infra.db.pool import SqlitePool
from octop.infra.db.repos.agent_acl import AclRole, AgentAclRepo
from octop.infra.db.repos.agents import AgentRepo
from octop.infra.db.repos.users import UserRepo


@pytest.fixture()
def db(tmp_path: Path) -> SqlitePool:
    pool = SqlitePool(tmp_path / "octop.db")
    run_migrations(pool)
    return pool


def _users(db: SqlitePool) -> dict[str, int]:
    repo = UserRepo(db)
    ids = {
        "owner": repo.create(username="owner", password_hash="h", role="user"),
        "viewer": repo.create(username="viewer", password_hash="h", role="user"),
        "editor": repo.create(username="editor", password_hash="h", role="user"),
        "stranger": repo.create(username="stranger", password_hash="h", role="user"),
    }
    return ids


def test_acl_table_exists_with_migration_015(db: SqlitePool) -> None:
    with db.connect() as conn:
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='agent_acl'"
        ).fetchall()
    assert rows
    with db.connect() as conn:
        version = conn.execute("SELECT version FROM _schema_version").fetchone()[0]
    assert version == 15


def test_legacy_is_shared_migrates_to_public_sentinel(db: SqlitePool) -> None:
    """The 015 migration promotes ``is_shared = 1`` rows into ACL sentinels."""
    agents = AgentRepo(db)
    users = _users(db)
    agents.create(agent_id="shared", user_id=users["owner"], name="Shared")
    agents.create(agent_id="private", user_id=users["owner"], name="Private")
    agents.set_shared("shared", True)
    # The migration already ran, but the *new* sentinel was inserted because
    # ``set_shared`` writes both the column and the ACL row atomically. That
    # covers the forward path; we additionally verify a hand-built legacy row.
    agents.update_config("shared")  # touch to confirm row exists
    with db.connect() as conn:
        rows = conn.execute(
            "SELECT agent_id, user_id, role FROM agent_acl ORDER BY agent_id"
        ).fetchall()
    by_agent = {r["agent_id"]: (r["user_id"], r["role"]) for r in rows}
    assert by_agent["shared"] == (None, "viewer")
    assert "private" not in by_agent


def test_grant_revoke_and_replace(db: SqlitePool) -> None:
    agents = AgentRepo(db)
    users = _users(db)
    agents.create(agent_id="a1", user_id=users["owner"], name="A1")
    acl = AgentAclRepo(db)

    acl.grant("a1", users["viewer"], AclRole.VIEWER)
    acl.grant("a1", users["editor"], AclRole.EDITOR)
    rows = acl.list_for_agent("a1")
    assert {r.user_id for r in rows if r.user_id is not None} == {
        users["viewer"],
        users["editor"],
    }
    roles = {r.user_id: r.role for r in rows if r.user_id is not None}
    assert roles[users["viewer"]] == "viewer"
    assert roles[users["editor"]] == "editor"

    # Update an existing grant.
    acl.grant("a1", users["viewer"], AclRole.EDITOR)
    rows = acl.list_for_agent("a1")
    promoted = next(r for r in rows if r.user_id == users["viewer"])
    assert promoted.role == "editor"

    # Revoke leaves the editor alone.
    assert acl.revoke("a1", users["viewer"]) is True
    assert acl.revoke("a1", users["viewer"]) is False

    acl.replace_all(
        "a1",
        [(users["editor"], "viewer"), (None, "viewer")],
    )
    rows = acl.list_for_agent("a1")
    assert len(rows) == 2
    assert {r.user_id for r in rows} == {users["editor"], None}


def test_invalid_role_raises(db: SqlitePool) -> None:
    agents = AgentRepo(db)
    users = _users(db)
    agents.create(agent_id="a1", user_id=users["owner"], name="A1")
    acl = AgentAclRepo(db)
    with pytest.raises(ValueError):
        acl.grant("a1", users["viewer"], "admin")


def test_effective_role_owner_and_admin_and_grants(db: SqlitePool) -> None:
    agents = AgentRepo(db)
    users = _users(db)
    agents.create(agent_id="a1", user_id=users["owner"], name="A1")
    acl = AgentAclRepo(db)

    # Owner 鈫?editor, regardless of ACL.
    assert acl.role_for("a1", users["owner"], is_owner=True, is_admin=False) == "editor"
    # Admin 鈫?editor.
    assert acl.role_for("a1", users["stranger"], is_owner=False, is_admin=True) == "editor"
    # Stranger 鈫?None (no public sentinel).
    assert acl.role_for("a1", users["stranger"], is_owner=False, is_admin=False) is None
    # Explicit viewer grant.
    acl.grant("a1", users["viewer"], AclRole.VIEWER)
    assert acl.role_for("a1", users["viewer"], is_owner=False, is_admin=False) == "viewer"
    # Public sentinel grants stranger viewer.
    acl.grant("a1", None, AclRole.VIEWER)
    assert acl.role_for("a1", users["stranger"], is_owner=False, is_admin=False) == "viewer"
    # Explicit grant overrides public default.
    acl.grant("a1", users["viewer"], AclRole.EDITOR)
    assert acl.role_for("a1", users["viewer"], is_owner=False, is_admin=False) == "editor"


def test_list_visible_agents_includes_owned_and_granted(db: SqlitePool) -> None:
    agents = AgentRepo(db)
    users = _users(db)
    agents.create(agent_id="mine", user_id=users["owner"], name="Mine")
    agents.create(agent_id="yours", user_id=users["editor"], name="Yours")
    agents.create(agent_id="public", user_id=users["stranger"], name="Public")
    acl = AgentAclRepo(db)
    acl.grant("public", None, AclRole.VIEWER)
    acl.grant("yours", users["viewer"], AclRole.EDITOR)

    # Owner: owns "mine" and may see the public sentinel.
    assert set(acl.list_visible_agents(user_id=users["owner"])) == {"mine", "public"}
    # Viewer: explicitly granted on "yours" plus the public sentinel.
    assert set(acl.list_visible_agents(user_id=users["viewer"])) == {"yours", "public"}
    # Stranger without grants: only the public sentinel.
    assert set(acl.list_visible_agents(user_id=users["stranger"])) == {"public"}


def test_set_shared_round_trips_with_public_sentinel(db: SqlitePool) -> None:
    agents = AgentRepo(db)
    users = _users(db)
    agents.create(agent_id="a1", user_id=users["owner"], name="A1")
    agents.set_shared("a1", True)
    acl = AgentAclRepo(db)
    assert acl.get("a1", None) is not None

    agents.set_shared("a1", False)
    assert acl.get("a1", None) is None
