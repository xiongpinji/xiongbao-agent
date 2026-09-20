"""Tests for the CreditRepo + credit migration (v16)."""

from __future__ import annotations

from octop.infra.db.pool import DatabasePool, SqlitePool
from octop.infra.db.repos.credits import CreditRepo


def _bootstrap_user(pool: DatabasePool, username: str = "alice") -> int:
    with pool.transaction() as conn:
        conn.execute(
            "INSERT INTO users (username, password_hash, role, created_at) "
            "VALUES (?, ?, 'user', 1)",
            (username, "x" * 64),
        )
    with pool.connect() as conn:
        row = conn.execute(
            "SELECT id FROM users WHERE username = ?", (username,)
        ).fetchone()
    assert row is not None
    return int(row["id"])


def _make_pool(tmp_path) -> DatabasePool:
    pool = SqlitePool(tmp_path / "credits.sqlite")
    from octop.infra.db.migrate import run_migrations

    run_migrations(pool)
    return pool


def test_credit_tables_exist_after_migration(tmp_path):
    pool = _make_pool(tmp_path)
    with pool.connect() as conn:
        names = {row[0] for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()}
    assert "credit_account" in names
    assert "credit_ledger" in names
    pool.close()


def test_ensure_account_creates_default_free_tier(tmp_path):
    pool = _make_pool(tmp_path)
    user_id = _bootstrap_user(pool)
    repo = CreditRepo(pool)
    account = repo.ensure_account(user_id)
    assert account.user_id == user_id
    assert account.tier == "free"
    assert account.tier_name == "Free"
    assert account.balance == 0
    # ensure is idempotent
    again = repo.ensure_account(user_id)
    assert again.updated_at == account.updated_at
    pool.close()


def test_record_recharge_increments_balance_and_earned(tmp_path):
    pool = _make_pool(tmp_path)
    user_id = _bootstrap_user(pool)
    repo = CreditRepo(pool)
    repo.record(user_id=user_id, kind="recharge", amount=500, description="top-up")
    account = repo.get_account(user_id)
    assert account is not None
    assert account.balance == 500
    assert account.total_earned == 500
    assert account.total_spent == 0


def test_record_spend_decrements_balance_and_tracks_used(tmp_path):
    pool = _make_pool(tmp_path)
    user_id = _bootstrap_user(pool)
    repo = CreditRepo(pool)
    repo.update_tier(
        user_id,
        tier="pro",
        tier_name="Pro 专业版",
        monthly_allowance=5_000,
    )
    repo.record(user_id=user_id, kind="recharge", amount=100, description="seed")
    repo.record(user_id=user_id, kind="spend", amount=-30, description="model call")
    account = repo.get_account(user_id)
    assert account is not None
    assert account.balance == 70
    assert account.total_spent == 30
    assert account.monthly_used == 30


def test_list_ledger_returns_recent_rows_first(tmp_path):
    pool = _make_pool(tmp_path)
    user_id = _bootstrap_user(pool)
    repo = CreditRepo(pool)
    repo.record(user_id=user_id, kind="recharge", amount=100, description="seed", ts=100)
    repo.record(user_id=user_id, kind="spend", amount=-20, description="chat", ts=200)
    repo.record(user_id=user_id, kind="refund", amount=10, description="refund", ts=300)
    rows = repo.list_ledger(user_id=user_id)
    assert [r.ts for r in rows] == [300, 200, 100]
    assert [r.kind for r in rows] == ["refund", "spend", "recharge"]


def test_to_transaction_shape_matches_renderer_contract(tmp_path):
    pool = _make_pool(tmp_path)
    user_id = _bootstrap_user(pool)
    repo = CreditRepo(pool)
    ledger = repo.record(
        user_id=user_id,
        kind="spend",
        amount=-12,
        description="deep-research",
        category="model_usage",
        metadata={"model": "gpt-5", "tokens": 12_000},
    )
    payload = repo.to_transaction(ledger)
    assert payload["type"] == "spend"
    assert payload["amount"] == -12
    assert payload["description"] == "deep-research"
    assert payload["category"] == "model_usage"
    assert isinstance(payload["timestamp"], int)
    assert isinstance(payload["id"], str)


def test_summary_translates_tokens_to_credits(tmp_path):
    pool = _make_pool(tmp_path)
    user_id = _bootstrap_user(pool)
    repo = CreditRepo(pool)
    repo.update_tier(
        user_id,
        tier="pro",
        tier_name="Pro 专业版",
        monthly_allowance=5_000,
    )
    repo.record(user_id=user_id, kind="spend", amount=-300, description="x", metadata={"tokens": 300_000})
    summary = repo.to_summary(repo.get_account(user_id))
    assert summary["monthly_allowance"] == 5_000
    assert summary["monthly_used"] == 300
    assert summary["monthly_percent"] == 6  # 300/5_000 → 6 %


def test_record_usage_skips_zero_credit_spend(tmp_path):
    pool = _make_pool(tmp_path)
    user_id = _bootstrap_user(pool)
    repo = CreditRepo(pool)
    result = repo.record_usage(user_id=user_id, tokens=500, description="ping")
    assert result is None
    rows = repo.list_ledger(user_id=user_id)
    assert rows == []
