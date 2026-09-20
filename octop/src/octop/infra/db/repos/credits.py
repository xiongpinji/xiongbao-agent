"""Credit account and ledger access.

Credit is the user-facing denomination. Internally we also track raw token
usage so the API can answer "how much of my monthly allowance have I
spent?" without forcing the renderer to keep that state. The repo mirrors
the schema introduced in migration 016.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from octop.infra.db.pool import DatabasePool
from octop.infra.db.repos._base import DbRow, now_ts


_CREDIT_KIND_DEFAULT_TIER = {
    "free": ("Free", 0),
    "basic": ("Basic", 1_000_000),
    "pro": ("Pro 专业版", 5_000_000),
    "enterprise": ("Enterprise", 30_000_000),
}


@dataclass(frozen=True)
class CreditAccountRow:
    user_id: int
    balance: int
    total_earned: int
    total_spent: int
    tier: str
    tier_name: str
    monthly_allowance: int
    monthly_used: int
    monthly_window_start: int | None
    next_reset_at: int | None
    updated_at: int

    @classmethod
    def from_row(cls, r: DbRow) -> CreditAccountRow:
        return cls(
            user_id=r["user_id"],
            balance=int(r["balance"]),
            total_earned=int(r["total_earned"]),
            total_spent=int(r["total_spent"]),
            tier=str(r["tier"]),
            tier_name=str(r["tier_name"]),
            monthly_allowance=int(r["monthly_allowance"]),
            monthly_used=int(r["monthly_used"]),
            monthly_window_start=(
                int(r["monthly_window_start"])
                if r["monthly_window_start"] is not None
                else None
            ),
            next_reset_at=(
                int(r["next_reset_at"]) if r["next_reset_at"] is not None else None
            ),
            updated_at=int(r["updated_at"]),
        )


@dataclass(frozen=True)
class CreditLedgerRow:
    id: int
    user_id: int
    kind: str
    amount: int
    description: str
    category: str | None
    ref_id: str | None
    metadata: dict[str, Any] | None
    ts: int

    @classmethod
    def from_row(cls, r: DbRow) -> CreditLedgerRow:
        raw_meta = r["metadata"]
        metadata: dict[str, Any] | None
        if raw_meta is None:
            metadata = None
        else:
            try:
                metadata = json.loads(str(raw_meta))
            except (TypeError, ValueError):
                metadata = None
        return cls(
            id=int(r["id"]),
            user_id=int(r["user_id"]),
            kind=str(r["kind"]),
            amount=int(r["amount"]),
            description=str(r["description"]),
            category=str(r["category"]) if r["category"] is not None else None,
            ref_id=str(r["ref_id"]) if r["ref_id"] is not None else None,
            metadata=metadata,
            ts=int(r["ts"]),
        )


def _tokens_to_credits(tokens: int) -> int:
    """Translate raw token usage to the renderer-facing credit unit.

    The product spec uses 1 credit ≈ 1_000 tokens so a 1 M-token monthly
    allowance reads as 1_000 credits to the user. This conversion is kept
    here (and not in the renderer) so the renderer never has to know the
    token/credit ratio and historical ledgers stay interpretable.
    """
    return max(0, tokens // 1000)


def _credits_to_tokens(credits: int) -> int:
    return max(0, credits) * 1000


class CreditRepo:
    def __init__(self, db: DatabasePool):
        self._db = db

    # --- account ---------------------------------------------------------

    def get_account(self, user_id: int) -> CreditAccountRow | None:
        with self._db.connect() as conn:
            row = conn.execute(
                "SELECT * FROM credit_account WHERE user_id = ?",
                (user_id,),
            ).fetchone()
        return CreditAccountRow.from_row(row) if row else None

    def ensure_account(self, user_id: int, *, tier: str = "free") -> CreditAccountRow:
        existing = self.get_account(user_id)
        if existing is not None:
            return existing
        tier_name, allowance = _CREDIT_KIND_DEFAULT_TIER.get(
            tier, _CREDIT_KIND_DEFAULT_TIER["free"]
        )
        ts = now_ts()
        with self._db.transaction() as conn:
            conn.execute(
                """
                INSERT INTO credit_account (
                    user_id, balance, total_earned, total_spent,
                    tier, tier_name,
                    monthly_allowance, monthly_used,
                    updated_at
                ) VALUES (?, 0, 0, 0, ?, ?, ?, 0, ?)
                """,
                (
                    user_id,
                    tier,
                    tier_name,
                    allowance,
                    ts,
                ),
            )
        row = self.get_account(user_id)
        assert row is not None, "credit_account row missing after insert"
        return row

    def update_tier(
        self,
        user_id: int,
        *,
        tier: str,
        tier_name: str,
        monthly_allowance: int,
        next_reset_at: int | None = None,
    ) -> CreditAccountRow:
        """Switch tier + reset the monthly window. Used by admin tools."""
        account = self.ensure_account(user_id, tier=tier)
        ts = now_ts()
        with self._db.transaction() as conn:
            conn.execute(
                """
                UPDATE credit_account
                SET tier = ?, tier_name = ?, monthly_allowance = ?,
                    monthly_used = 0, monthly_window_start = ?,
                    next_reset_at = ?, updated_at = ?
                WHERE user_id = ?
                """,
                (
                    tier,
                    tier_name,
                    monthly_allowance,
                    ts,
                    next_reset_at,
                    ts,
                    user_id,
                ),
            )
        row = self.get_account(user_id)
        assert row is not None
        return row

    # --- ledger ----------------------------------------------------------

    def record(
        self,
        *,
        user_id: int,
        kind: str,
        amount: int,
        description: str = "",
        category: str | None = None,
        ref_id: str | None = None,
        metadata: dict[str, Any] | None = None,
        ts: int | None = None,
    ) -> CreditLedgerRow:
        """Append a ledger row and atomically adjust the account totals."""
        if amount == 0:
            raise ValueError("credit ledger rows must have a non-zero amount")
        ts_value = ts or now_ts()
        meta_json = json.dumps(metadata, sort_keys=True) if metadata else None
        with self._db.transaction() as conn:
            # Make sure the account exists so a freshly-registered user can
            # receive an initial recharge without us having to seed rows up
            # front.
            self._ensure_account_in_conn(conn, user_id)
            conn.execute(
                """
                INSERT INTO credit_ledger (
                    user_id, kind, amount, description, category, ref_id, metadata, ts
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    user_id,
                    kind,
                    amount,
                    description,
                    category,
                    ref_id,
                    meta_json,
                    ts_value,
                ),
            )
            earned_delta = amount if amount > 0 else 0
            spent_delta = -amount if amount < 0 else 0
            used_delta = spent_delta
            conn.execute(
                """
                UPDATE credit_account
                SET balance = balance + ?,
                    total_earned = total_earned + ?,
                    total_spent = total_spent + ?,
                    monthly_used = MAX(0, monthly_used + ?),
                    updated_at = ?
                WHERE user_id = ?
                """,
                (
                    amount,
                    earned_delta,
                    spent_delta,
                    used_delta,
                    ts_value,
                    user_id,
                ),
            )
        latest = self.list_ledger(user_id=user_id, limit=1)
        return latest[0]

    def apply_token_spend(
        self,
        *,
        user_id: int,
        tokens: int,
        description: str = "",
        ref_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> tuple[CreditLedgerRow | None, int]:
        """Debit a user's credit balance for a model call.

        Returns ``(ledger_row, credits_debited)``. ``ledger_row`` is
        ``None`` when the spend rounds to zero credits so trivial calls
        don't pollute the ledger. ``credits_debited`` reports the actual
        token usage so the caller can record its own metric.
        """
        if tokens <= 0:
            return None, 0
        credits = tokens // 1000
        meta = {**(metadata or {}), "tokens": tokens}
        if credits <= 0:
            # Sub-credit usage still bumps the raw counter so the monthly
            # window keeps progressing for high-frequency low-token calls.
            self._bump_token_usage(user_id, tokens)
            return None, 0
        row = self.record(
            user_id=user_id,
            kind="spend",
            amount=-credits,
            description=description,
            category="model_usage",
            ref_id=ref_id,
            metadata=meta,
        )
        return row, credits

    def list_ledger(
        self,
        *,
        user_id: int,
        kind: str | None = None,
        limit: int = 200,
    ) -> list[CreditLedgerRow]:
        sql = "SELECT * FROM credit_ledger WHERE user_id = ?"
        params: list[Any] = [user_id]
        if kind is not None:
            sql += " AND kind = ?"
            params.append(kind)
        sql += " ORDER BY ts DESC, id DESC LIMIT ?"
        params.append(max(1, int(limit)))
        with self._db.connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [CreditLedgerRow.from_row(r) for r in rows]

    def export_ledger(self, *, user_id: int, limit: int = 50_000) -> list[CreditLedgerRow]:
        cap = max(1, min(int(limit), 50_000))
        with self._db.connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM (
                    SELECT * FROM credit_ledger
                    WHERE user_id = ?
                    ORDER BY ts DESC, id DESC
                    LIMIT ?
                ) AS recent
                ORDER BY ts ASC, id ASC
                """,
                (user_id, cap),
            ).fetchall()
        return [CreditLedgerRow.from_row(r) for r in rows]

    # --- helpers ---------------------------------------------------------

    def to_summary(self, account: CreditAccountRow) -> dict[str, Any]:
        # The schema stores the user-facing credit denomination directly so
        # the renderer never has to know the credit/token conversion ratio.
        allowance = account.monthly_allowance
        used = account.monthly_used
        percent = (
            min(100, used * 100 // allowance) if allowance else 0
        )
        return {
            "balance": account.balance,
            "total_earned": account.total_earned,
            "total_spent": account.total_spent,
            "tier": account.tier,
            "tier_name": account.tier_name,
            "monthly_allowance": allowance,
            "monthly_used": used,
            "monthly_allowance_tokens": allowance,
            "monthly_used_tokens": used,
            "monthly_percent": percent,
            "next_reset_at": account.next_reset_at,
            "updated_at": account.updated_at,
        }

    def to_transaction(self, row: CreditLedgerRow) -> dict[str, Any]:
        return {
            "id": str(row.id),
            "type": row.kind,
            "amount": row.amount,
            "description": row.description,
            "category": row.category,
            "timestamp": row.ts,
        }

    def record_usage(
        self,
        *,
        user_id: int,
        tokens: int,
        description: str,
        ref_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> CreditLedgerRow | None:
        """Translate a model-call's token usage into a credit ledger debit.

        Returns ``None`` when the token spend rounds to zero credits so
        trivial calls (single-token pings, etc.) don't pollute the ledger.
        """
        credits = tokens // 1000
        if credits <= 0:
            return None
        return self.record(
            user_id=user_id,
            kind="spend",
            amount=-credits,
            description=description,
            category="model_usage",
            ref_id=ref_id,
            metadata={**(metadata or {}), "tokens": tokens},
        )

    def _ensure_account_in_conn(self, conn: Any, user_id: int) -> None:
        row = conn.execute(
            "SELECT 1 FROM credit_account WHERE user_id = ?", (user_id,)
        ).fetchone()
        if row is not None:
            return
        ts = now_ts()
        conn.execute(
            """
            INSERT INTO credit_account (
                user_id, balance, total_earned, total_spent,
                tier, tier_name,
                monthly_allowance, monthly_used,
                updated_at
            ) VALUES (?, 0, 0, 0, 'free', 'Free', 0, 0, ?)
            """,
            (user_id, ts),
        )
