"""ACL-aware agent access checks (P1-3).

The historical ``is_shared`` column migrated to ``agent_acl`` rows where
``user_id IS NULL`` represents "public-readable". The functions here
prefer the ACL table when present, fall back to the legacy column when
the migration hasn't been applied yet, and never silently widen access.
"""

from __future__ import annotations

from typing import Any

from octop.infra.db.repos.agent_acl import AclRole, AgentAclRepo
from octop.infra.errors import ErrorCode, OctopError


def _acl_repo(server: Any) -> AgentAclRepo | None:
    repo = getattr(getattr(server, "services", None), "agent_acl_repo", None)
    return repo if isinstance(repo, AgentAclRepo) else None


def effective_role(
    server: Any,
    row: Any,
    user: Any,
    *,
    user_id: int | None = None,
) -> str | None:
    """Return ``'editor'`` / ``'viewer'`` / ``None`` for the user on the agent.

    ``user_id`` defaults to ``user.id``; admins and owners always get
    ``'editor'``; explicit ACL rows take precedence; the public-readable
    sentinel is consulted as a fallback.
    """
    if user is None:
        return None
    if user_id is None:
        user_id = getattr(user, "id", None)
    is_owner = getattr(row, "user_id", None) is not None and row.user_id == user_id
    if user.is_admin or is_owner:
        return AclRole.EDITOR.value
    repo = _acl_repo(server)
    if repo is None:
        # Pre-migration fallback: rely on the boolean column.
        return AclRole.VIEWER.value if int(getattr(row, "is_shared", 0) or 0) == 1 else None
    return repo.role_for(
        getattr(row, "agent_id", None) or row.id,
        user_id,
        is_owner=is_owner,
        is_admin=user.is_admin,
    )


def user_may_view(server: Any, row: Any, user: Any) -> bool:
    return effective_role(server, row, user) is not None


def user_may_edit(server: Any, row: Any, user: Any) -> bool:
    return effective_role(server, row, user) == AclRole.EDITOR.value


def assert_agent_view(server: Any, row: Any, user: Any) -> None:
    if not user_may_view(server, row, user):
        raise OctopError(ErrorCode.FORBIDDEN, "agent not accessible to user")


def assert_agent_edit(server: Any, row: Any, user: Any) -> None:
    if not user_may_edit(server, row, user):
        raise OctopError(ErrorCode.FORBIDDEN, "agent is not editable by user")


def public_acl_present(server: Any, row: Any) -> bool:
    """``True`` when the agent currently has a public-readable ACL row.

    Mirrors the old ``is_shared`` boolean so existing dashboards keep
    rendering the "shared" badge without an extra schema read.
    """
    repo = _acl_repo(server)
    if repo is None:
        return int(getattr(row, "is_shared", 0) or 0) == 1
    sentinel = repo.get(getattr(row, "agent_id", None) or row.id, None)
    return sentinel is not None
