"""Per-agent access control list.

P1-3 deliverable. Each row grants ``viewer`` (read + chat) or ``editor``
(create / update / delete) rights on one agent to one user. A row with
``user_id = NULL`` is the public-readable sentinel (the legacy
``is_shared = 1`` row is migrated to that form by migration 015).

The agent owner (the row's ``agents.user_id``) is always implicitly an
editor; ACL rows are additive. Callers should treat the owner as
authoritative and never insert a duplicate ACL row for the owner.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from octop.infra.db.pool import DatabasePool
from octop.infra.db.repos._base import now_ts


class AclRole(StrEnum):
    VIEWER = "viewer"
    EDITOR = "editor"


_VALID_ROLES = frozenset(role.value for role in AclRole)


@dataclass(frozen=True)
class AclRow:
    id: int
    agent_id: str
    user_id: int | None  # NULL → public-readable
    role: str
    created_at: int
    updated_at: int

    @classmethod
    def from_row(cls, r) -> AclRow:  # type: ignore[no-untyped-def]
        return cls(
            id=int(r["id"]),
            agent_id=str(r["agent_id"]),
            user_id=r["user_id"],
            role=str(r["role"]),
            created_at=int(r["created_at"]),
            updated_at=int(r["updated_at"]),
        )

    @property
    def is_public(self) -> bool:
        return self.user_id is None


class AgentAclRepo:
    """CRUD for the ``agent_acl`` table."""

    def __init__(self, db: DatabasePool) -> None:
        self._db = db

    # ---- writes ---------------------------------------------------------

    def grant(
        self,
        agent_id: str,
        user_id: int | None,
        role: str | AclRole,
        *,
        replace: bool = True,
    ) -> None:
        """Insert or update a single ACL row.

        ``user_id=None`` represents the public-readable sentinel.
        Raises ``ValueError`` on an unknown role.
        """
        role_str = role.value if isinstance(role, AclRole) else str(role)
        if role_str not in _VALID_ROLES:
            raise ValueError(f"invalid acl role: {role_str!r}")
        ts = now_ts()
        with self._db.transaction() as conn:
            if replace:
                conn.execute(
                    "DELETE FROM agent_acl WHERE agent_id = ? AND user_id IS ?",
                    (agent_id, user_id),
                )
            try:
                conn.execute(
                    "INSERT INTO agent_acl(agent_id, user_id, role, created_at, updated_at) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (agent_id, user_id, role_str, ts, ts),
                )
            except Exception as exc:  # pragma: no cover - surfaced as OctopError upstream
                # Unique-constraint conflict: the row already exists; update it
                # instead of failing. ``replace=True`` covers the common path.
                if "unique" not in str(exc).lower():
                    raise
                conn.execute(
                    "UPDATE agent_acl SET role = ?, updated_at = ? "
                    "WHERE agent_id = ? AND user_id IS ?",
                    (role_str, ts, agent_id, user_id),
                )

    def revoke(self, agent_id: str, user_id: int | None) -> bool:
        """Delete one ACL row. Returns True when a row was actually removed."""
        with self._db.transaction() as conn:
            cur = conn.execute(
                "DELETE FROM agent_acl WHERE agent_id = ? AND user_id IS ?",
                (agent_id, user_id),
            )
            return bool(cur.rowcount > 0)

    def replace_all(
        self,
        agent_id: str,
        grants: list[tuple[int | None, str]],
    ) -> None:
        """Replace the full ACL for ``agent_id`` with the given grants.

        ``grants`` is a list of ``(user_id, role)`` pairs; ``user_id=None``
        represents the public-readable sentinel. Any pre-existing rows for
        this agent are removed first, so the caller controls the exact set.

        ``user_id`` of the owner is silently skipped — the owner is always
        an implicit editor.
        """
        ts = now_ts()
        with self._db.transaction() as conn:
            conn.execute("DELETE FROM agent_acl WHERE agent_id = ?", (agent_id,))
            for user_id, role in grants:
                role_str = role.value if isinstance(role, AclRole) else str(role)
                if role_str not in _VALID_ROLES:
                    raise ValueError(f"invalid acl role: {role_str!r}")
                conn.execute(
                    "INSERT INTO agent_acl(agent_id, user_id, role, created_at, updated_at) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (agent_id, user_id, role_str, ts, ts),
                )

    # ---- reads ----------------------------------------------------------

    def list_for_agent(self, agent_id: str) -> list[AclRow]:
        with self._db.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM agent_acl WHERE agent_id = ? "
                "ORDER BY user_id IS NULL DESC, user_id ASC",
                (agent_id,),
            ).fetchall()
        return [AclRow.from_row(r) for r in rows]

    def get(self, agent_id: str, user_id: int | None) -> AclRow | None:
        with self._db.connect() as conn:
            r = conn.execute(
                "SELECT * FROM agent_acl WHERE agent_id = ? AND user_id IS ?",
                (agent_id, user_id),
            ).fetchone()
        return AclRow.from_row(r) if r else None

    def role_for(
        self,
        agent_id: str,
        user_id: int | None,
        *,
        is_owner: bool,
        is_admin: bool,
    ) -> str | None:
        """Resolve the effective role for a viewer.

        Returns ``'editor'``, ``'viewer'``, or ``None`` when the user has no
        access. Admins always see ``'editor'`` so they can recover stuck
        agents. Owners always see ``'editor'`` regardless of ACL rows.
        """
        if is_admin or is_owner:
            return AclRole.EDITOR.value
        if user_id is None:
            row = self.get(agent_id, None)
            return row.role if row else None
        row = self.get(agent_id, user_id)
        if row is not None:
            return row.role
        # Fall back to the public sentinel when the user has no explicit grant.
        pub = self.get(agent_id, None)
        return pub.role if pub else None

    def list_visible_agents(
        self,
        *,
        user_id: int,
        include_disabled: bool = True,
    ) -> list[str]:
        """Return ``agent_id`` values ``user_id`` is allowed to see.

        Owned + editor/viewer + public-readable agents all qualify.
        Used to extend ``AgentRepo.list_by_user`` without breaking it.
        """
        sql = (
            "SELECT DISTINCT a.agent_id FROM agents a "
            "LEFT JOIN agent_acl acl "
            "  ON acl.agent_id = a.agent_id "
            " AND (acl.user_id = ? OR acl.user_id IS NULL) "
            "WHERE (a.user_id = ? OR acl.id IS NOT NULL)"
        )
        params: list[object] = [user_id, user_id]
        if not include_disabled:
            sql += " AND a.enabled = 1"
        with self._db.connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [str(r["agent_id"]) for r in rows]
