"""Credit router — account / ledger / recharge for the current user.

  GET    /api/credits/account        — caller summary (auto-creates on first hit)
  GET    /api/credits/ledger        — caller's ledger rows
  POST   /api/credits/recharge      — record a top-up (server-side stub)
  GET    /api/admin/credits/ledger  — admin: arbitrary user's ledger

The router only exposes the current user's own credits. Admin overrides
live under the ``admin_router`` (mounted under ``/api/admin/credits``).

Recharge is intentionally a no-op stub: a real payment provider is
out of scope for this milestone. The endpoint persists the ledger row,
which means QA / smoke flows can prove the entire path end-to-end.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from octop.api.deps import current_user, get_server
from octop.infra.errors import ErrorCode, OctopError


router = APIRouter()


class RechargeBody(BaseModel):
    credits: int = Field(gt=0, le=1_000_000)
    description: str = "Top-up"


class AdminLedgerQuery(BaseModel):
    user_id: int = Field(gt=0)
    limit: int = Field(default=200, gt=0, le=50_000)


def _summary(server: Any, user_id: int) -> dict[str, Any]:
    account = server.services.credit_repo.ensure_account(user_id)
    return server.services.credit_repo.to_summary(account)


def _transactions(server: Any, user_id: int, limit: int = 200) -> list[dict[str, Any]]:
    rows = server.services.credit_repo.list_ledger(user_id=user_id, limit=limit)
    return [server.services.credit_repo.to_transaction(r) for r in rows]


@router.get("/credits/account", summary="Current user's credit account summary")
async def get_account(
    user: Any = Depends(current_user),
    server: Any = Depends(get_server),
) -> dict[str, Any]:
    return _summary(server, int(user.id))


@router.get("/credits/ledger", summary="Current user's credit ledger entries")
async def get_ledger(
    limit: int = 200,
    user: Any = Depends(current_user),
    server: Any = Depends(get_server),
) -> dict[str, Any]:
    return {
        "transactions": _transactions(server, int(user.id), limit=limit),
    }


@router.post(
    "/credits/recharge",
    summary="Record a top-up for the current user (stub: no payment integration yet)",
)
async def post_recharge(
    body: RechargeBody,
    user: Any = Depends(current_user),
    server: Any = Depends(get_server),
) -> dict[str, Any]:
    ledger = server.services.credit_repo.record(
        user_id=int(user.id),
        kind="recharge",
        amount=body.credits,
        description=body.description,
        category="manual_top_up",
    )
    return {
        "transaction": server.services.credit_repo.to_transaction(ledger),
        "account": _summary(server, int(user.id)),
    }


# --- admin --------------------------------------------------------------

admin_router = APIRouter()


@admin_router.get("/credits/ledger", summary="Admin: arbitrary user's credit ledger")
async def admin_ledger(
    user_id: int,
    limit: int = 200,
    user: Any = Depends(current_user),
    server: Any = Depends(get_server),
) -> dict[str, Any]:
    if not getattr(user, "is_admin", False):
        raise OctopError(ErrorCode.FORBIDDEN, "admin required")
    target = server.user_manager.get_by_id(user_id)
    if target is None:
        raise OctopError(ErrorCode.NOT_FOUND, "user not found")
    return {
        "user_id": int(target.id),
        "transactions": _transactions(server, int(target.id), limit=limit),
    }


@admin_router.post(
    "/credits/tier",
    summary="Admin: switch a user's tier and reset their monthly window",
)
async def admin_tier(
    user_id: int,
    tier: str = "free",
    tier_name: str = "Free",
    monthly_allowance: int = 0,
    next_reset_at: int | None = None,
    user: Any = Depends(current_user),
    server: Any = Depends(get_server),
) -> dict[str, Any]:
    if not getattr(user, "is_admin", False):
        raise OctopError(ErrorCode.FORBIDDEN, "admin required")
    if tier not in {"free", "basic", "pro", "enterprise"}:
        raise OctopError(ErrorCode.VALIDATION, "unknown tier")
    target = server.user_manager.get_by_id(user_id)
    if target is None:
        raise OctopError(ErrorCode.NOT_FOUND, "user not found")
    server.services.credit_repo.update_tier(
        user_id=int(target.id),
        tier=tier,
        tier_name=tier_name,
        monthly_allowance=max(0, monthly_allowance),
        next_reset_at=next_reset_at,
    )
    return _summary(server, int(target.id))
