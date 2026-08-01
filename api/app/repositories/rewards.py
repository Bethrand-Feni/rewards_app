from __future__ import annotations

from app.db import Database, DbStatement


LIST_FOR_PARENT = """
SELECT id, family_id, name, description, point_cost, r2_image_key,
       is_active, created_by_user_id, created_at, updated_at
FROM rewards
WHERE family_id = ?1
ORDER BY created_at DESC, id DESC
"""

LIST_FOR_CHILD = """
SELECT id, family_id, name, description, point_cost, r2_image_key,
       is_active, created_by_user_id, created_at, updated_at
FROM rewards
WHERE family_id = ?1
  AND is_active = 1
ORDER BY created_at DESC, id DESC
"""

FIND_REWARD = """
SELECT id, family_id, name, description, point_cost, r2_image_key,
       is_active, created_by_user_id, created_at, updated_at
FROM rewards
WHERE id = ?1
  AND family_id = ?2
LIMIT 1
"""

CREATE_REWARD = """
INSERT INTO rewards (
  id, family_id, name, description, point_cost, created_by_user_id,
  created_at, updated_at
) VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?7)
"""

UPDATE_REWARD = """
UPDATE rewards
SET name = ?1, description = ?2, point_cost = ?3, updated_at = ?4
WHERE id = ?5
  AND family_id = ?6
"""

DEACTIVATE_REWARD = """
UPDATE rewards
SET is_active = 0, updated_at = ?1
WHERE id = ?2
  AND family_id = ?3
"""

UPDATE_IMAGE = """
UPDATE rewards
SET r2_image_key = ?1, updated_at = ?2
WHERE id = ?3
  AND family_id = ?4
"""

CREATE_REDEMPTION = """
INSERT INTO reward_redemptions (
  id, family_id, reward_id, child_user_id, point_cost_snapshot,
  reward_name_snapshot, status, created_at, updated_at
) VALUES (?1, ?2, ?3, ?4, ?5, ?6, 'PENDING', ?7, ?7)
"""

REDEMPTION_SELECT = """
SELECT
  rr.id, rr.family_id, rr.reward_id, rr.child_user_id,
  rr.point_cost_snapshot, rr.reward_name_snapshot, rr.status,
  rr.review_comment, rr.reviewed_by_user_id, rr.reviewed_at,
  rr.created_at, rr.updated_at,
  COALESCE(rr.reward_name_snapshot, r.name) AS reward_name,
  u.display_name AS child_name
FROM reward_redemptions AS rr
JOIN rewards AS r ON r.id = rr.reward_id
JOIN users AS u ON u.id = rr.child_user_id
"""

MINE = REDEMPTION_SELECT + """
WHERE rr.family_id = ?1
  AND rr.child_user_id = ?2
ORDER BY rr.created_at DESC, rr.id DESC
LIMIT 50
"""

PENDING = REDEMPTION_SELECT + """
WHERE rr.family_id = ?1
  AND rr.status = 'PENDING'
ORDER BY rr.created_at, rr.id
"""

FIND_REDEMPTION = """
SELECT
  id, family_id, reward_id, child_user_id, point_cost_snapshot,
  reward_name_snapshot, status, review_comment, reviewed_by_user_id,
  reviewed_at, created_at, updated_at
FROM reward_redemptions
WHERE id = ?1
  AND family_id = ?2
LIMIT 1
"""

APPROVE_REDEMPTION = """
UPDATE reward_redemptions
SET status = 'APPROVED', review_comment = ?1, reviewed_by_user_id = ?2,
    reviewed_at = ?3, updated_at = ?3
WHERE id = ?4
  AND family_id = ?5
  AND status = 'PENDING'
  AND EXISTS (
    SELECT 1
    FROM point_transactions
    WHERE family_id = ?5
      AND redemption_id = ?4
      AND transaction_type = 'REWARD_REDEMPTION'
  )
"""

REJECT_REDEMPTION = """
UPDATE reward_redemptions
SET status = 'REJECTED', review_comment = ?1, reviewed_by_user_id = ?2,
    reviewed_at = ?3, updated_at = ?3
WHERE id = ?4
  AND family_id = ?5
  AND status = 'PENDING'
"""


class RewardRepository:
    def __init__(self, db: Database):
        self.db = db

    async def list_for_family(self, family_id: str, child: bool) -> list[dict]:
        return await self.db.many(
            LIST_FOR_CHILD if child else LIST_FOR_PARENT, family_id
        )

    async def find_by_id(self, reward_id: str, family_id: str) -> dict | None:
        return await self.db.one(FIND_REWARD, reward_id, family_id)

    async def create(
        self,
        reward_id: str,
        family_id: str,
        name: str,
        description: str,
        point_cost: int,
        created_by_user_id: str,
        now: str,
    ) -> None:
        await self.db.execute(
            CREATE_REWARD,
            reward_id,
            family_id,
            name,
            description,
            point_cost,
            created_by_user_id,
            now,
        )

    async def update(
        self,
        reward_id: str,
        family_id: str,
        name: str,
        description: str,
        point_cost: int,
        now: str,
    ) -> int:
        result = await self.db.execute(
            UPDATE_REWARD,
            name,
            description,
            point_cost,
            now,
            reward_id,
            family_id,
        )
        return result.changes

    async def deactivate(
        self, reward_id: str, family_id: str, now: str
    ) -> int:
        result = await self.db.execute(
            DEACTIVATE_REWARD, now, reward_id, family_id
        )
        return result.changes

    async def update_image(
        self,
        reward_id: str,
        family_id: str,
        object_key: str,
        now: str,
    ) -> int:
        result = await self.db.execute(
            UPDATE_IMAGE, object_key, now, reward_id, family_id
        )
        return result.changes

    async def create_redemption(
        self,
        redemption_id: str,
        family_id: str,
        reward_id: str,
        child_user_id: str,
        point_cost: int,
        reward_name: str,
        now: str,
    ) -> None:
        await self.db.execute(
            CREATE_REDEMPTION,
            redemption_id,
            family_id,
            reward_id,
            child_user_id,
            point_cost,
            reward_name,
            now,
        )

    async def list_mine(
        self, family_id: str, child_user_id: str
    ) -> list[dict]:
        return await self.db.many(MINE, family_id, child_user_id)

    async def list_pending(self, family_id: str) -> list[dict]:
        return await self.db.many(PENDING, family_id)

    async def find_redemption(
        self, redemption_id: str, family_id: str
    ) -> dict | None:
        return await self.db.one(FIND_REDEMPTION, redemption_id, family_id)

    def approve_statement(
        self,
        redemption_id: str,
        family_id: str,
        comment: str,
        reviewer_id: str,
        now: str,
    ) -> DbStatement:
        return DbStatement(
            APPROVE_REDEMPTION,
            (comment, reviewer_id, now, redemption_id, family_id),
        )

    async def reject(
        self,
        redemption_id: str,
        family_id: str,
        comment: str,
        reviewer_id: str,
        now: str,
    ) -> int:
        result = await self.db.execute(
            REJECT_REDEMPTION,
            comment,
            reviewer_id,
            now,
            redemption_id,
            family_id,
        )
        return result.changes
