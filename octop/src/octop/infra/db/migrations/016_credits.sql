-- Schema v16: credit accounts and ledger.
--
-- A user owns exactly one credit_account row (balance, lifetime totals,
-- tier, monthly allowance, next reset timestamp). Every balance change is
-- appended to credit_ledger with a positive or negative amount so the
-- monthly allowance / monthly used figures can be recomputed from the
-- ledger without losing audit history.
--
-- ``tier`` follows the product line: free / basic / pro / enterprise.
-- ``monthly_allowance_tokens`` is the soft cap on monthly usage in tokens;
-- the renderer translates this to a UI "credits" amount via the conversion
-- ratio the renderer carries.

CREATE TABLE credit_account (
  user_id                    INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
  balance                    INTEGER NOT NULL DEFAULT 0,
  total_earned               INTEGER NOT NULL DEFAULT 0,
  total_spent                INTEGER NOT NULL DEFAULT 0,
  tier                       TEXT    NOT NULL DEFAULT 'free'
                             CHECK (tier IN ('free', 'basic', 'pro', 'enterprise')),
  tier_name                  TEXT    NOT NULL DEFAULT 'Free',
  monthly_allowance          INTEGER NOT NULL DEFAULT 0,
  monthly_used               INTEGER NOT NULL DEFAULT 0,
  monthly_window_start       INTEGER,
  next_reset_at              INTEGER,
  updated_at                 INTEGER NOT NULL
);

CREATE TABLE credit_ledger (
  id           INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id      INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  -- spend | earn | recharge | gift | refund
  kind         TEXT    NOT NULL CHECK (kind IN ('spend', 'earn', 'recharge', 'gift', 'refund')),
  -- signed delta; positive credits the user, negative debits them.
  amount       INTEGER NOT NULL,
  description  TEXT    NOT NULL DEFAULT '',
  category     TEXT,
  ref_id       TEXT,
  -- model_calls, prompt_tokens, completion_tokens (only when kind = spend)
  metadata     TEXT,
  ts           INTEGER NOT NULL
);

CREATE INDEX idx_credit_ledger_user_ts ON credit_ledger (user_id, ts DESC);
CREATE INDEX idx_credit_ledger_kind   ON credit_ledger (user_id, kind, ts DESC);

UPDATE _schema_version SET version = 16;
