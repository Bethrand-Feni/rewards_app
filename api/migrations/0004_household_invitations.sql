PRAGMA foreign_keys = ON;

CREATE TABLE household_invites (
  id TEXT PRIMARY KEY,
  family_id TEXT NOT NULL REFERENCES families(id),
  role TEXT NOT NULL CHECK (role IN ('PARENT', 'CHILD')),
  pin_hash TEXT NOT NULL,
  expires_at TEXT NOT NULL,
  consumed_at TEXT,
  created_by_user_id TEXT NOT NULL REFERENCES users(id),
  created_at TEXT NOT NULL
);

CREATE UNIQUE INDEX household_invites_family_pin
ON household_invites(family_id, pin_hash)
WHERE consumed_at IS NULL;

CREATE INDEX household_invites_expiry
ON household_invites(family_id, expires_at)
WHERE consumed_at IS NULL;
