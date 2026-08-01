PRAGMA foreign_keys = ON;

ALTER TABLE users ADD COLUMN account_type TEXT NOT NULL DEFAULT 'ACCOUNT'
  CHECK (account_type IN ('ACCOUNT', 'CHILD_PROFILE'));

ALTER TABLE family_members ADD COLUMN claimed_at TEXT;

CREATE TABLE child_join_invites (
  id TEXT PRIMARY KEY,
  family_id TEXT NOT NULL REFERENCES families(id),
  child_user_id TEXT NOT NULL REFERENCES users(id),
  pin_hash TEXT NOT NULL,
  expires_at TEXT NOT NULL,
  consumed_at TEXT,
  created_at TEXT NOT NULL,
  UNIQUE (child_user_id)
);

CREATE UNIQUE INDEX child_join_invites_family_pin
ON child_join_invites(family_id, pin_hash)
WHERE consumed_at IS NULL;

CREATE INDEX child_join_invites_expiry
ON child_join_invites(family_id, expires_at)
WHERE consumed_at IS NULL;
