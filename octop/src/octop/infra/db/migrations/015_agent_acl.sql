-- Schema v15: per-agent ACL (explicit collaborators).
-- Replaces the boolean ``is_shared`` column with a row-per-grantee model so
-- owners can grant view / edit rights to specific users without broadcasting
-- the agent to every tenant. Existing ``is_shared = 1`` rows become
-- "public-readable" by inserting a sentinel ACL row with user_id = NULL.

CREATE TABLE agent_acl (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  agent_id   TEXT    NOT NULL REFERENCES agents(agent_id) ON DELETE CASCADE,
  user_id    INTEGER REFERENCES users(id) ON DELETE CASCADE,
  role       TEXT    NOT NULL CHECK (role IN ('viewer', 'editor')),
  created_at INTEGER NOT NULL,
  updated_at INTEGER NOT NULL,
  UNIQUE(agent_id, user_id)
);

-- Public-readable sentinel: NULL user_id means "anyone can view".
CREATE UNIQUE INDEX idx_agent_acl_public
  ON agent_acl (agent_id)
  WHERE user_id IS NULL;

-- Pre-populate ACL from existing shared agents so the new model is a superset
-- of the old behaviour. Agents marked shared with no specific user get a
-- public-readable row (NULL user_id). Owners are implicit editors and need
-- not be duplicated here.
INSERT INTO agent_acl (agent_id, user_id, role, created_at, updated_at)
SELECT agent_id, NULL, 'viewer', created_at, updated_at
FROM agents
WHERE is_shared = 1;

UPDATE _schema_version SET version = 15;
