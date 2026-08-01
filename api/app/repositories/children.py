from __future__ import annotations

from app.db import Database, DbStatement


LIST_FOR_FAMILY = """
SELECT
  u.id,
  u.display_name,
  u.is_active,
  u.deletion_scheduled_for,
  u.created_at,
  CASE WHEN u.account_type = 'ACCOUNT' THEN 'CLAIMED' ELSE 'WAITING' END AS claim_status,
  i.expires_at AS join_pin_expires_at
FROM family_members AS fm
JOIN users AS u ON u.id = fm.user_id
LEFT JOIN child_join_invites AS i
  ON i.child_user_id = u.id AND i.consumed_at IS NULL
WHERE fm.family_id = ?1
  AND fm.role = 'CHILD'
ORDER BY u.display_name COLLATE NOCASE, u.id
"""

FIND_IN_FAMILY = """
SELECT u.id, u.display_name, u.is_active, u.account_type,
       fm.id AS member_id, fm.family_id
FROM users AS u
JOIN family_members AS fm ON fm.user_id = u.id
WHERE u.id = ?1
  AND fm.family_id = ?2
  AND fm.role = 'CHILD'
LIMIT 1
"""

CREATE_USER = """
INSERT INTO users (
  id, display_name, credential_hash, credential_salt, account_type,
  password_login_enabled, created_at, updated_at
) VALUES (?1, ?2, ?3, ?4, 'CHILD_PROFILE', 0, ?5, ?5)
"""

CREATE_MEMBER = """
INSERT INTO family_members (
  id, family_id, user_id, role, joined_at
) VALUES (?1, ?2, ?3, 'CHILD', ?4)
"""

UPDATE_USER = """
UPDATE users
SET display_name = ?1, updated_at = ?2
WHERE id = ?3
"""

UPSERT_JOIN_INVITE = """
INSERT INTO child_join_invites (
  id, family_id, child_user_id, pin_hash, expires_at, created_at
) VALUES (?1, ?2, ?3, ?4, ?5, ?6)
ON CONFLICT(child_user_id) DO UPDATE SET
  id = excluded.id,
  pin_hash = excluded.pin_hash,
  expires_at = excluded.expires_at,
  consumed_at = NULL,
  created_at = excluded.created_at
"""

FIND_JOIN_INVITE = """
SELECT i.id, i.family_id, i.child_user_id, i.expires_at,
       fm.id AS member_id, u.display_name
FROM child_join_invites AS i
JOIN users AS u ON u.id = i.child_user_id
JOIN family_members AS fm ON fm.user_id = u.id AND fm.family_id = i.family_id
WHERE i.family_id = ?1
  AND i.pin_hash = ?2
  AND i.consumed_at IS NULL
  AND i.expires_at > ?3
  AND u.account_type = 'CHILD_PROFILE'
  AND u.is_active = 1
LIMIT 1
"""

FIND_MEMBERSHIP = """
SELECT id FROM family_members WHERE user_id = ?1 LIMIT 1
"""

TRANSFER_CHORES = "UPDATE chores SET assigned_to_user_id = ?1 WHERE assigned_to_user_id = ?2"
TRANSFER_OCCURRENCES = "UPDATE chore_occurrences SET assigned_to_user_id = ?1 WHERE assigned_to_user_id = ?2"
TRANSFER_SUBMISSIONS = "UPDATE submissions SET child_user_id = ?1 WHERE child_user_id = ?2"
TRANSFER_POINTS = "UPDATE point_transactions SET user_id = ?1 WHERE user_id = ?2"
TRANSFER_REDEMPTIONS = "UPDATE reward_redemptions SET child_user_id = ?1 WHERE child_user_id = ?2"
TRANSFER_NOTIFICATIONS = "UPDATE notification_outbox SET recipient_user_id = ?1 WHERE recipient_user_id = ?2"
TRANSFER_MEMBER = """
UPDATE family_members SET user_id = ?1, claimed_at = ?2
WHERE id = ?3 AND user_id = ?4
"""
DELETE_INVITE = "DELETE FROM child_join_invites WHERE id = ?1"
DELETE_PROFILE = "DELETE FROM users WHERE id = ?1 AND account_type = 'CHILD_PROFILE'"

DEACTIVATE = """
UPDATE users
SET is_active = 0, updated_at = ?1
WHERE id = ?2
"""

REVOKE_SESSIONS = """
UPDATE auth_sessions
SET revoked_at = ?1
WHERE user_id = ?2
  AND revoked_at IS NULL
"""


class ChildRepository:
    def __init__(self, db: Database):
        self.db = db

    async def list_for_family(self, family_id: str) -> list[dict]:
        return await self.db.many(LIST_FOR_FAMILY, family_id)

    async def find_in_family(self, child_id: str, family_id: str) -> dict | None:
        return await self.db.one(FIND_IN_FAMILY, child_id, family_id)

    async def membership_for_user(self, user_id: str) -> dict | None:
        return await self.db.one(FIND_MEMBERSHIP, user_id)

    async def find_join_invite(
        self, family_id: str, pin_hash: str, now: str
    ) -> dict | None:
        return await self.db.one(
            FIND_JOIN_INVITE, family_id, pin_hash, now
        )

    def create_statements(
        self,
        child_id: str,
        member_id: str,
        family_id: str,
        display_name: str,
        credential_hash: str,
        credential_salt: str,
        now: str,
    ) -> list[DbStatement]:
        return [
            DbStatement(
                CREATE_USER,
                (
                    child_id,
                    display_name,
                    credential_hash,
                    credential_salt,
                    now,
                ),
            ),
            DbStatement(
                CREATE_MEMBER,
                (member_id, family_id, child_id, now),
            ),
        ]

    def update_statements(
        self,
        child_id: str,
        family_id: str,
        display_name: str,
        now: str,
    ) -> list[DbStatement]:
        return [DbStatement(UPDATE_USER, (display_name, now, child_id))]

    async def upsert_join_invite(
        self, invite_id: str, family_id: str, child_id: str,
        pin_hash: str, expires_at: str, now: str
    ) -> None:
        await self.db.execute(
            UPSERT_JOIN_INVITE,
            invite_id, family_id, child_id, pin_hash, expires_at, now
        )

    def claim_statements(
        self, account_id: str, invite: dict, now: str
    ) -> list[DbStatement]:
        profile_id = invite["child_user_id"]
        return [
            DbStatement(TRANSFER_CHORES, (account_id, profile_id)),
            DbStatement(TRANSFER_OCCURRENCES, (account_id, profile_id)),
            DbStatement(TRANSFER_SUBMISSIONS, (account_id, profile_id)),
            DbStatement(TRANSFER_POINTS, (account_id, profile_id)),
            DbStatement(TRANSFER_REDEMPTIONS, (account_id, profile_id)),
            DbStatement(TRANSFER_NOTIFICATIONS, (account_id, profile_id)),
            DbStatement(
                TRANSFER_MEMBER,
                (account_id, now, invite["member_id"], profile_id),
            ),
            DbStatement(DELETE_INVITE, (invite["id"],)),
            DbStatement(DELETE_PROFILE, (profile_id,)),
        ]

    def deactivate_statements(self, child_id: str, now: str) -> list[DbStatement]:
        return [
            DbStatement(DEACTIVATE, (now, child_id)),
            DbStatement(REVOKE_SESSIONS, (now, child_id)),
        ]
