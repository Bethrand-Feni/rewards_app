PRAGMA foreign_keys = ON;

CREATE TABLE families (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  access_code TEXT NOT NULL UNIQUE,
  created_at TEXT NOT NULL
);

CREATE TABLE users (
  id TEXT PRIMARY KEY,
  email TEXT UNIQUE,
  display_name TEXT NOT NULL,
  credential_hash TEXT NOT NULL,
  credential_salt TEXT NOT NULL,
  is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE family_members (
  id TEXT PRIMARY KEY,
  family_id TEXT NOT NULL REFERENCES families(id),
  user_id TEXT NOT NULL UNIQUE REFERENCES users(id),
  role TEXT NOT NULL CHECK (role IN ('PARENT', 'CHILD')),
  username TEXT,
  joined_at TEXT NOT NULL,
  UNIQUE (family_id, username)
);

CREATE TABLE auth_sessions (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL REFERENCES users(id),
  refresh_token_hash TEXT NOT NULL UNIQUE,
  expires_at TEXT NOT NULL,
  revoked_at TEXT,
  created_at TEXT NOT NULL
);

CREATE TABLE login_attempts (
  identity_hash TEXT PRIMARY KEY,
  attempts INTEGER NOT NULL DEFAULT 0,
  locked_until TEXT,
  updated_at TEXT NOT NULL
);

CREATE TABLE chores (
  id TEXT PRIMARY KEY,
  family_id TEXT NOT NULL REFERENCES families(id),
  title TEXT NOT NULL,
  description TEXT NOT NULL DEFAULT '',
  suggested_points INTEGER NOT NULL CHECK (suggested_points > 0),
  mode TEXT NOT NULL CHECK (mode IN ('REUSABLE', 'ONE_TIME')),
  assigned_to_user_id TEXT REFERENCES users(id),
  state TEXT NOT NULL DEFAULT 'ACTIVE' CHECK (state IN ('ACTIVE', 'LOCKED', 'COMPLETED', 'INACTIVE')),
  created_by_user_id TEXT NOT NULL REFERENCES users(id),
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE submissions (
  id TEXT PRIMARY KEY,
  family_id TEXT NOT NULL REFERENCES families(id),
  child_user_id TEXT NOT NULL REFERENCES users(id),
  chore_id TEXT REFERENCES chores(id),
  submission_type TEXT NOT NULL CHECK (submission_type IN ('CHORE', 'OTHER_ACTIVITY')),
  title TEXT NOT NULL,
  description TEXT NOT NULL DEFAULT '',
  status TEXT NOT NULL CHECK (status IN ('PENDING', 'APPROVED', 'REJECTED', 'CHANGES_REQUESTED')),
  locks_chore INTEGER NOT NULL DEFAULT 0 CHECK (locks_chore IN (0, 1)),
  current_revision INTEGER NOT NULL DEFAULT 1,
  awarded_points INTEGER CHECK (awarded_points IS NULL OR awarded_points > 0),
  review_comment TEXT,
  reviewed_by_user_id TEXT REFERENCES users(id),
  reviewed_at TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE UNIQUE INDEX one_active_submission_per_child_chore
ON submissions(child_user_id, chore_id)
WHERE chore_id IS NOT NULL AND status IN ('PENDING', 'CHANGES_REQUESTED');

CREATE UNIQUE INDEX one_active_lock_per_one_time_chore
ON submissions(chore_id)
WHERE chore_id IS NOT NULL AND locks_chore = 1
  AND status IN ('PENDING', 'CHANGES_REQUESTED');

CREATE TABLE submission_images (
  id TEXT PRIMARY KEY,
  submission_id TEXT NOT NULL REFERENCES submissions(id),
  revision INTEGER NOT NULL,
  r2_object_key TEXT NOT NULL UNIQUE,
  content_type TEXT NOT NULL,
  file_size INTEGER NOT NULL,
  created_at TEXT NOT NULL,
  UNIQUE (submission_id, revision)
);

CREATE TABLE point_transactions (
  id TEXT PRIMARY KEY,
  family_id TEXT NOT NULL REFERENCES families(id),
  user_id TEXT NOT NULL REFERENCES users(id),
  transaction_type TEXT NOT NULL CHECK (
    transaction_type IN ('SUBMISSION_REWARD', 'REWARD_REDEMPTION', 'MANUAL_ADJUSTMENT', 'REVERSAL')
  ),
  amount INTEGER NOT NULL CHECK (amount <> 0),
  submission_id TEXT REFERENCES submissions(id),
  redemption_id TEXT,
  reason TEXT NOT NULL,
  created_by_user_id TEXT NOT NULL REFERENCES users(id),
  created_at TEXT NOT NULL
);

CREATE UNIQUE INDEX one_points_award_per_submission
ON point_transactions(submission_id)
WHERE submission_id IS NOT NULL AND transaction_type = 'SUBMISSION_REWARD';

CREATE TABLE rewards (
  id TEXT PRIMARY KEY,
  family_id TEXT NOT NULL REFERENCES families(id),
  name TEXT NOT NULL,
  description TEXT NOT NULL DEFAULT '',
  point_cost INTEGER NOT NULL CHECK (point_cost > 0),
  r2_image_key TEXT,
  is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
  created_by_user_id TEXT NOT NULL REFERENCES users(id),
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE reward_redemptions (
  id TEXT PRIMARY KEY,
  family_id TEXT NOT NULL REFERENCES families(id),
  reward_id TEXT NOT NULL REFERENCES rewards(id),
  child_user_id TEXT NOT NULL REFERENCES users(id),
  point_cost_snapshot INTEGER NOT NULL CHECK (point_cost_snapshot > 0),
  status TEXT NOT NULL CHECK (status IN ('PENDING', 'APPROVED', 'REJECTED')),
  review_comment TEXT,
  reviewed_by_user_id TEXT REFERENCES users(id),
  reviewed_at TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE UNIQUE INDEX one_pending_redemption_per_reward
ON reward_redemptions(child_user_id, reward_id)
WHERE status = 'PENDING';

CREATE UNIQUE INDEX one_points_deduction_per_redemption
ON point_transactions(redemption_id)
WHERE redemption_id IS NOT NULL AND transaction_type = 'REWARD_REDEMPTION';

CREATE INDEX submissions_family_status ON submissions(family_id, status, created_at DESC);
CREATE INDEX transactions_user_created ON point_transactions(user_id, created_at DESC);
CREATE INDEX redemptions_family_status ON reward_redemptions(family_id, status, created_at DESC);
