PRAGMA foreign_keys = ON;

ALTER TABLE families ADD COLUMN timezone TEXT NOT NULL DEFAULT 'Africa/Johannesburg';
ALTER TABLE families ADD COLUMN deletion_scheduled_for TEXT;

ALTER TABLE users ADD COLUMN password_login_enabled INTEGER NOT NULL DEFAULT 1
  CHECK (password_login_enabled IN (0, 1));
ALTER TABLE users ADD COLUMN deletion_scheduled_for TEXT;

CREATE TABLE auth_identities (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL REFERENCES users(id),
  provider TEXT NOT NULL CHECK (provider IN ('GOOGLE')),
  provider_subject TEXT NOT NULL,
  verified_email TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE (provider, provider_subject),
  UNIQUE (provider, user_id)
);

CREATE TABLE oauth_nonces (
  id TEXT PRIMARY KEY,
  nonce_hash TEXT NOT NULL UNIQUE,
  expires_at TEXT NOT NULL,
  used_at TEXT,
  created_at TEXT NOT NULL
);

CREATE TABLE deletion_requests (
  id TEXT PRIMARY KEY,
  target_type TEXT NOT NULL CHECK (target_type IN ('FAMILY', 'CHILD')),
  target_id TEXT NOT NULL,
  family_id TEXT NOT NULL REFERENCES families(id),
  requested_by_user_id TEXT NOT NULL REFERENCES users(id),
  execute_after TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'PENDING'
    CHECK (status IN ('PENDING', 'CANCELLED', 'COMPLETED', 'FAILED')),
  last_error TEXT,
  created_at TEXT NOT NULL,
  cancelled_at TEXT,
  completed_at TEXT
);

CREATE UNIQUE INDEX one_pending_deletion_per_target
ON deletion_requests(target_type, target_id)
WHERE status = 'PENDING';

ALTER TABLE chores ADD COLUMN schedule_type TEXT NOT NULL DEFAULT 'NONE'
  CHECK (schedule_type IN ('NONE', 'ONCE', 'DAILY', 'WEEKDAYS'));
ALTER TABLE chores ADD COLUMN start_date TEXT;
ALTER TABLE chores ADD COLUMN due_local_time TEXT;
ALTER TABLE chores ADD COLUMN weekday_mask INTEGER NOT NULL DEFAULT 0
  CHECK (weekday_mask >= 0 AND weekday_mask <= 127);
ALTER TABLE chores ADD COLUMN reminders_enabled INTEGER NOT NULL DEFAULT 1
  CHECK (reminders_enabled IN (0, 1));

CREATE TABLE chore_occurrences (
  id TEXT PRIMARY KEY,
  chore_id TEXT NOT NULL REFERENCES chores(id),
  family_id TEXT NOT NULL REFERENCES families(id),
  assigned_to_user_id TEXT REFERENCES users(id),
  title_snapshot TEXT NOT NULL,
  description_snapshot TEXT NOT NULL DEFAULT '',
  points_snapshot INTEGER NOT NULL CHECK (points_snapshot > 0),
  local_due_date TEXT NOT NULL,
  due_at TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'OPEN'
    CHECK (status IN ('OPEN', 'OVERDUE', 'SUBMITTED', 'COMPLETED', 'MISSED', 'CANCELLED')),
  reminder_sent_at TEXT,
  overdue_notified_at TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE (chore_id, local_due_date)
);

CREATE INDEX chore_occurrences_family_status_due
ON chore_occurrences(family_id, status, due_at);

ALTER TABLE submissions ADD COLUMN chore_occurrence_id TEXT REFERENCES chore_occurrences(id);

CREATE UNIQUE INDEX one_active_submission_per_occurrence
ON submissions(chore_occurrence_id)
WHERE chore_occurrence_id IS NOT NULL
  AND status IN ('PENDING', 'CHANGES_REQUESTED');

ALTER TABLE reward_redemptions ADD COLUMN reward_name_snapshot TEXT;
UPDATE reward_redemptions
SET reward_name_snapshot = (
  SELECT rewards.name FROM rewards WHERE rewards.id = reward_redemptions.reward_id
)
WHERE reward_name_snapshot IS NULL;

CREATE TABLE push_devices (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL REFERENCES users(id),
  family_id TEXT NOT NULL REFERENCES families(id),
  installation_id TEXT NOT NULL,
  expo_push_token TEXT NOT NULL,
  platform TEXT NOT NULL CHECK (platform IN ('ANDROID', 'IOS')),
  is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE (user_id, installation_id),
  UNIQUE (expo_push_token)
);

CREATE INDEX push_devices_family_active
ON push_devices(family_id, is_active);

CREATE TABLE notification_outbox (
  id TEXT PRIMARY KEY,
  family_id TEXT NOT NULL REFERENCES families(id),
  recipient_user_id TEXT NOT NULL REFERENCES users(id),
  notification_type TEXT NOT NULL,
  title TEXT NOT NULL,
  body TEXT NOT NULL,
  route TEXT NOT NULL,
  idempotency_key TEXT NOT NULL UNIQUE,
  status TEXT NOT NULL DEFAULT 'PENDING'
    CHECK (status IN ('PENDING', 'SENT', 'DELIVERED', 'RETRY', 'FAILED')),
  expo_ticket_id TEXT,
  attempts INTEGER NOT NULL DEFAULT 0,
  next_attempt_at TEXT NOT NULL,
  sent_at TEXT,
  delivered_at TEXT,
  last_error TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE INDEX notification_outbox_pending
ON notification_outbox(status, next_attempt_at);
