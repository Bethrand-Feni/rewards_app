from __future__ import annotations

from app.db import Database, DbStatement


CREATE_INVITE = """
INSERT INTO household_invites (
  id, family_id, role, pin_hash, expires_at,
  created_by_user_id, created_at
) VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7)
"""

FIND_INVITE = """
SELECT id, family_id, role, expires_at
FROM household_invites
WHERE family_id = ?1
  AND pin_hash = ?2
  AND consumed_at IS NULL
  AND expires_at > ?3
LIMIT 1
"""

CREATE_MEMBER_FROM_INVITE = """
INSERT INTO family_members (
  id, family_id, user_id, role, joined_at, claimed_at
)
SELECT ?1, family_id, ?2, role, ?3, ?3
FROM household_invites
WHERE id = ?4
  AND consumed_at IS NULL
  AND expires_at > ?3
"""

CONSUME_INVITE = """
UPDATE household_invites
SET consumed_at = ?1
WHERE id = ?2
  AND consumed_at IS NULL
"""

LIST_MEMBERS = """
SELECT
  u.id,
  u.display_name,
  u.is_active,
  u.deletion_scheduled_for,
  u.created_at,
  u.account_type,
  fm.role,
  fm.joined_at
FROM family_members AS fm
JOIN users AS u ON u.id = fm.user_id
WHERE fm.family_id = ?1
ORDER BY CASE fm.role WHEN 'PARENT' THEN 0 ELSE 1 END,
         u.display_name COLLATE NOCASE,
         u.id
"""


class HouseholdInviteRepository:
    def __init__(self, db: Database):
        self.db = db

    async def create(
        self,
        invite_id: str,
        family_id: str,
        role: str,
        pin_hash: str,
        expires_at: str,
        created_by_user_id: str,
        now: str,
    ) -> None:
        await self.db.execute(
            CREATE_INVITE,
            invite_id,
            family_id,
            role,
            pin_hash,
            expires_at,
            created_by_user_id,
            now,
        )

    async def find(
        self, family_id: str, pin_hash: str, now: str
    ) -> dict | None:
        return await self.db.one(FIND_INVITE, family_id, pin_hash, now)

    def redeem_statements(
        self, member_id: str, user_id: str, invite_id: str, now: str
    ) -> list[DbStatement]:
        return [
            DbStatement(
                CREATE_MEMBER_FROM_INVITE,
                (member_id, user_id, now, invite_id),
            ),
            DbStatement(CONSUME_INVITE, (now, invite_id)),
        ]

    async def list_members(self, family_id: str) -> list[dict]:
        return await self.db.many(LIST_MEMBERS, family_id)
