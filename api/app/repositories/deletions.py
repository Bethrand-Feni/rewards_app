from __future__ import annotations

from app.db import Database, DbStatement


FAMILY_NAME = """
SELECT name FROM families WHERE id = ?1 LIMIT 1
"""

CHILD = """
SELECT u.id, u.display_name
FROM users AS u
JOIN family_members AS fm ON fm.user_id = u.id
WHERE u.id = ?1
  AND fm.family_id = ?2
  AND fm.role = 'CHILD'
LIMIT 1
"""

CREATE_REQUEST = """
INSERT INTO deletion_requests (
  id, target_type, target_id, family_id, requested_by_user_id,
  execute_after, created_at
) VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7)
"""

MARK_FAMILY = """
UPDATE families SET deletion_scheduled_for = ?1 WHERE id = ?2
"""

REVOKE_CHILDREN = """
UPDATE auth_sessions
SET revoked_at = ?1
WHERE user_id IN (
  SELECT user_id
  FROM family_members
  WHERE family_id = ?2
    AND role = 'CHILD'
)
AND revoked_at IS NULL
"""

MARK_CHILD = """
UPDATE users
SET is_active = 0, deletion_scheduled_for = ?1, updated_at = ?2
WHERE id = ?3
"""

REVOKE_CHILD = """
UPDATE auth_sessions
SET revoked_at = ?1
WHERE user_id = ?2
  AND revoked_at IS NULL
"""

CANCEL_REQUEST = """
UPDATE deletion_requests
SET status = 'CANCELLED', cancelled_at = ?1
WHERE target_type = ?2
  AND target_id = ?3
  AND family_id = ?4
  AND status = 'PENDING'
"""

CLEAR_FAMILY = """
UPDATE families SET deletion_scheduled_for = NULL WHERE id = ?1
"""

RESTORE_CHILD = """
UPDATE users
SET is_active = 1, deletion_scheduled_for = NULL, updated_at = ?1
WHERE id = ?2
"""

DUE = """
SELECT
  id, target_type, target_id, family_id, requested_by_user_id,
  execute_after, status, last_error, created_at, cancelled_at, completed_at
FROM deletion_requests
WHERE status = 'PENDING'
  AND execute_after <= ?1
ORDER BY execute_after, id
LIMIT 10
"""

CHILD_IMAGE_KEYS = """
SELECT si.r2_object_key
FROM submission_images AS si
JOIN submissions AS s ON s.id = si.submission_id
WHERE s.family_id = ?1
  AND s.child_user_id = ?2
ORDER BY si.r2_object_key
"""

FAMILY_IMAGE_KEYS = """
SELECT si.r2_object_key AS object_key
FROM submission_images AS si
JOIN submissions AS s ON s.id = si.submission_id
WHERE s.family_id = ?1
UNION ALL
SELECT r.r2_image_key AS object_key
FROM rewards AS r
WHERE r.family_id = ?1
  AND r.r2_image_key IS NOT NULL
"""

FAMILY_USER_IDS = """
SELECT user_id AS id
FROM family_members
WHERE family_id = ?1
ORDER BY user_id
"""

FAIL_REQUEST = """
UPDATE deletion_requests
SET status = 'FAILED', last_error = ?1
WHERE id = ?2
  AND status = 'PENDING'
"""


class DeletionRepository:
    def __init__(self, db: Database):
        self.db = db

    async def family_name(self, family_id: str) -> str | None:
        row = await self.db.one(FAMILY_NAME, family_id)
        return row["name"] if row else None

    async def child(
        self, child_id: str, family_id: str
    ) -> dict | None:
        return await self.db.one(CHILD, child_id, family_id)

    def schedule_family_statements(
        self,
        request_id: str,
        family_id: str,
        requester_id: str,
        execute_after: str,
        now: str,
    ) -> list[DbStatement]:
        return [
            DbStatement(
                CREATE_REQUEST,
                (
                    request_id,
                    "FAMILY",
                    family_id,
                    family_id,
                    requester_id,
                    execute_after,
                    now,
                ),
            ),
            DbStatement(MARK_FAMILY, (execute_after, family_id)),
            DbStatement(REVOKE_CHILDREN, (now, family_id)),
        ]

    def schedule_child_statements(
        self,
        request_id: str,
        child_id: str,
        family_id: str,
        requester_id: str,
        execute_after: str,
        now: str,
    ) -> list[DbStatement]:
        return [
            DbStatement(
                CREATE_REQUEST,
                (
                    request_id,
                    "CHILD",
                    child_id,
                    family_id,
                    requester_id,
                    execute_after,
                    now,
                ),
            ),
            DbStatement(MARK_CHILD, (execute_after, now, child_id)),
            DbStatement(REVOKE_CHILD, (now, child_id)),
        ]

    async def cancel(
        self,
        target_type: str,
        target_id: str,
        family_id: str,
        now: str,
    ) -> int:
        result = await self.db.execute(
            CANCEL_REQUEST,
            now,
            target_type,
            target_id,
            family_id,
        )
        return result.changes

    async def clear_family_schedule(self, family_id: str) -> None:
        await self.db.execute(CLEAR_FAMILY, family_id)

    async def restore_child(self, child_id: str, now: str) -> None:
        await self.db.execute(RESTORE_CHILD, now, child_id)

    async def due(self, now: str) -> list[dict]:
        return await self.db.many(DUE, now)

    async def child_image_keys(
        self, family_id: str, child_id: str
    ) -> list[str]:
        return [
            row["r2_object_key"]
            for row in await self.db.many(
                CHILD_IMAGE_KEYS, family_id, child_id
            )
        ]

    async def family_image_keys(self, family_id: str) -> list[str]:
        return [
            row["object_key"]
            for row in await self.db.many(FAMILY_IMAGE_KEYS, family_id)
        ]

    async def family_user_ids(self, family_id: str) -> list[str]:
        return [
            row["id"]
            for row in await self.db.many(FAMILY_USER_IDS, family_id)
        ]

    async def fail(self, request_id: str, error: str) -> None:
        await self.db.execute(FAIL_REQUEST, error[:500], request_id)

    @staticmethod
    def child_purge_statements(
        deletion_id: str, family_id: str, child_id: str
    ) -> list[DbStatement]:
        sql_params = [
            (
                "UPDATE chores SET assigned_to_user_id = NULL "
                "WHERE family_id = ?1 AND assigned_to_user_id = ?2",
                (family_id, child_id),
            ),
            (
                "UPDATE chore_occurrences SET assigned_to_user_id = NULL "
                "WHERE family_id = ?1 AND assigned_to_user_id = ?2",
                (family_id, child_id),
            ),
            (
                "DELETE FROM notification_outbox "
                "WHERE family_id = ?1 AND recipient_user_id = ?2",
                (family_id, child_id),
            ),
            (
                "DELETE FROM push_devices "
                "WHERE family_id = ?1 AND user_id = ?2",
                (family_id, child_id),
            ),
            (
                "DELETE FROM point_transactions "
                "WHERE family_id = ?1 AND user_id = ?2",
                (family_id, child_id),
            ),
            (
                "DELETE FROM submission_images WHERE submission_id IN ("
                "SELECT id FROM submissions "
                "WHERE family_id = ?1 AND child_user_id = ?2)",
                (family_id, child_id),
            ),
            (
                "DELETE FROM submissions "
                "WHERE family_id = ?1 AND child_user_id = ?2",
                (family_id, child_id),
            ),
            (
                "DELETE FROM reward_redemptions "
                "WHERE family_id = ?1 AND child_user_id = ?2",
                (family_id, child_id),
            ),
            (
                "DELETE FROM auth_sessions WHERE user_id = ?1",
                (child_id,),
            ),
            (
                "DELETE FROM auth_identities WHERE user_id = ?1",
                (child_id,),
            ),
            (
                "DELETE FROM deletion_requests WHERE id = ?1",
                (deletion_id,),
            ),
            (
                "DELETE FROM family_members "
                "WHERE family_id = ?1 AND user_id = ?2",
                (family_id, child_id),
            ),
            ("DELETE FROM users WHERE id = ?1", (child_id,)),
        ]
        return [DbStatement(sql, params) for sql, params in sql_params]

    @staticmethod
    def family_purge_statements(
        family_id: str, user_ids: list[str]
    ) -> list[DbStatement]:
        statements = [
            DbStatement(
                "DELETE FROM notification_outbox WHERE family_id = ?1",
                (family_id,),
            ),
            DbStatement(
                "DELETE FROM push_devices WHERE family_id = ?1",
                (family_id,),
            ),
            DbStatement(
                "DELETE FROM point_transactions WHERE family_id = ?1",
                (family_id,),
            ),
        ]
        statements.extend(
            [
                DbStatement(
                    "DELETE FROM submission_images WHERE submission_id IN ("
                    "SELECT id FROM submissions WHERE family_id = ?1)",
                    (family_id,),
                ),
                DbStatement(
                    "DELETE FROM submissions WHERE family_id = ?1",
                    (family_id,),
                ),
                DbStatement(
                    "DELETE FROM reward_redemptions WHERE family_id = ?1",
                    (family_id,),
                ),
                DbStatement(
                    "DELETE FROM rewards WHERE family_id = ?1",
                    (family_id,),
                ),
                DbStatement(
                    "DELETE FROM chore_occurrences WHERE family_id = ?1",
                    (family_id,),
                ),
                DbStatement(
                    "DELETE FROM chores WHERE family_id = ?1",
                    (family_id,),
                ),
                DbStatement(
                    "DELETE FROM deletion_requests WHERE family_id = ?1",
                    (family_id,),
                ),
            ]
        )
        for user_id in user_ids:
            statements.extend(
                [
                    DbStatement(
                        "DELETE FROM auth_sessions WHERE user_id = ?1",
                        (user_id,),
                    ),
                    DbStatement(
                        "DELETE FROM auth_identities WHERE user_id = ?1",
                        (user_id,),
                    ),
                ]
            )
        statements.append(
            DbStatement(
                "DELETE FROM family_members WHERE family_id = ?1",
                (family_id,),
            )
        )
        statements.extend(
            DbStatement("DELETE FROM users WHERE id = ?1", (user_id,))
            for user_id in user_ids
        )
        statements.append(
            DbStatement("DELETE FROM families WHERE id = ?1", (family_id,))
        )
        return statements
