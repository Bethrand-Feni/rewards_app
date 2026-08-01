from __future__ import annotations

from app.db import Database, DbStatement


LIST_FOR_CHILD = """
SELECT
  c.id, c.family_id, c.title, c.description, c.suggested_points, c.mode,
  c.assigned_to_user_id, c.state, c.created_by_user_id, c.created_at,
  c.updated_at, COALESCE(c.schedule_frequency, c.schedule_type) AS schedule_type,
  c.schedule_frequency, c.start_date, c.due_local_time,
  c.weekday_mask, c.reminders_enabled,
  u.display_name AS assigned_to_name,
  co.id AS occurrence_id, co.due_at, co.local_due_date,
  co.status AS occurrence_status,
  COALESCE(co.title_snapshot, c.title) AS display_title,
  COALESCE(co.description_snapshot, c.description) AS display_description,
  COALESCE(co.points_snapshot, c.suggested_points) AS display_points
FROM chores AS c
LEFT JOIN users AS u ON u.id = c.assigned_to_user_id
LEFT JOIN chore_occurrences AS co
  ON co.chore_id = c.id
 AND co.family_id = c.family_id
 AND co.status IN ('OPEN', 'OVERDUE')
WHERE c.family_id = ?1
  AND c.state = 'ACTIVE'
  AND (c.assigned_to_user_id IS NULL OR c.assigned_to_user_id = ?2)
  AND (c.schedule_type = 'NONE' OR co.id IS NOT NULL)
ORDER BY COALESCE(co.due_at, c.created_at), c.id
"""

LIST_FOR_PARENT = """
SELECT
  c.id, c.family_id, c.title, c.description, c.suggested_points, c.mode,
  c.assigned_to_user_id, c.state, c.created_by_user_id, c.created_at,
  c.updated_at, COALESCE(c.schedule_frequency, c.schedule_type) AS schedule_type,
  c.schedule_frequency, c.start_date, c.due_local_time,
  c.weekday_mask, c.reminders_enabled,
  u.display_name AS assigned_to_name,
  (
    SELECT co.due_at
    FROM chore_occurrences AS co
    WHERE co.chore_id = c.id
      AND co.family_id = c.family_id
      AND co.status IN ('OPEN', 'OVERDUE')
    ORDER BY co.due_at, co.id
    LIMIT 1
  ) AS next_due_at,
  (
    SELECT co.status
    FROM chore_occurrences AS co
    WHERE co.chore_id = c.id
      AND co.family_id = c.family_id
      AND co.status IN ('OPEN', 'OVERDUE')
    ORDER BY co.due_at, co.id
    LIMIT 1
  ) AS next_occurrence_status
FROM chores AS c
LEFT JOIN users AS u ON u.id = c.assigned_to_user_id
WHERE c.family_id = ?1
  AND c.state != 'INACTIVE'
ORDER BY c.created_at DESC, c.id DESC
"""

FIND = """
SELECT
  id, family_id, title, description, suggested_points, mode,
  assigned_to_user_id, state, created_by_user_id, created_at, updated_at,
  COALESCE(schedule_frequency, schedule_type) AS schedule_type,
  schedule_frequency, start_date, due_local_time, weekday_mask, reminders_enabled
FROM chores
WHERE id = ?1
  AND family_id = ?2
LIMIT 1
"""

CREATE = """
INSERT INTO chores (
  id, family_id, title, description, suggested_points, mode,
  assigned_to_user_id, schedule_type, schedule_frequency, start_date,
  due_local_time, weekday_mask, reminders_enabled, created_by_user_id,
  created_at, updated_at
) VALUES (
  ?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8, ?9, ?10, ?11, ?12, ?13, ?14, ?15, ?15
)
"""

UPDATE = """
UPDATE chores
SET title = ?1, description = ?2, suggested_points = ?3, mode = ?4,
    assigned_to_user_id = ?5, schedule_type = ?6, schedule_frequency = ?7,
    start_date = ?8, due_local_time = ?9, weekday_mask = ?10,
    reminders_enabled = ?11, updated_at = ?12
WHERE id = ?13
  AND family_id = ?14
  AND state = 'ACTIVE'
"""

DELETE_FUTURE_OPEN = """
DELETE FROM chore_occurrences
WHERE chore_id = ?1
  AND family_id = ?2
  AND due_at > ?3
  AND status = 'OPEN'
  AND NOT EXISTS (
    SELECT 1
    FROM submissions AS s
    WHERE s.chore_occurrence_id = chore_occurrences.id
      AND s.family_id = ?2
  )
"""

DEACTIVATE = """
UPDATE chores
SET state = 'INACTIVE', updated_at = ?1
WHERE id = ?2
  AND family_id = ?3
"""

CANCEL_OPEN = """
UPDATE chore_occurrences
SET status = 'CANCELLED', updated_at = ?1
WHERE chore_id = ?2
  AND family_id = ?3
  AND status = 'OPEN'
"""

COMPLETE_ONE_TIME = """
UPDATE chores
SET state = 'COMPLETED', updated_at = ?1
WHERE id = ?2
  AND family_id = ?3
  AND mode = 'ONE_TIME'
"""

REOPEN_ONE_TIME = """
UPDATE chores
SET state = 'ACTIVE', updated_at = ?1
WHERE id = ?2
  AND family_id = ?3
  AND mode = 'ONE_TIME'
  AND state = 'LOCKED'
"""

ACTIVE_FAMILIES = """
SELECT id, timezone
FROM families
WHERE deletion_scheduled_for IS NULL
ORDER BY id
"""

SCHEDULED_FOR_FAMILY = """
SELECT
  id, family_id, title, description, suggested_points, mode,
  assigned_to_user_id, state, created_by_user_id, created_at, updated_at,
  schedule_type, schedule_frequency, start_date, due_local_time,
  weekday_mask, reminders_enabled
FROM chores
WHERE family_id = ?1
  AND state = 'ACTIVE'
  AND schedule_type != 'NONE'
  AND start_date IS NOT NULL
  AND due_local_time IS NOT NULL
ORDER BY id
"""

CREATE_OCCURRENCE = """
INSERT OR IGNORE INTO chore_occurrences (
  id, chore_id, family_id, assigned_to_user_id, title_snapshot,
  description_snapshot, points_snapshot, local_due_date, due_at,
  created_at, updated_at
) VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8, ?9, ?10, ?10)
"""

MISS_OLDER = """
UPDATE chore_occurrences
SET status = 'MISSED', updated_at = ?1
WHERE chore_id = ?2
  AND family_id = ?3
  AND due_at < ?4
  AND status IN ('OPEN', 'OVERDUE')
"""

DUE_OCCURRENCES = """
SELECT
  co.id, co.chore_id, co.family_id, co.assigned_to_user_id,
  co.title_snapshot, co.due_at
FROM chore_occurrences AS co
WHERE co.status = 'OPEN'
  AND co.due_at <= ?1
ORDER BY co.due_at, co.id
"""

MARK_OVERDUE = """
UPDATE chore_occurrences
SET status = 'OVERDUE', overdue_notified_at = ?1, updated_at = ?1
WHERE id = ?2
  AND family_id = ?3
  AND status = 'OPEN'
"""

REMINDERS = """
SELECT
  co.id, co.family_id, co.assigned_to_user_id, co.title_snapshot, co.due_at
FROM chore_occurrences AS co
JOIN chores AS c
  ON c.id = co.chore_id
 AND c.family_id = co.family_id
WHERE co.status = 'OPEN'
  AND c.reminders_enabled = 1
  AND co.reminder_sent_at IS NULL
  AND co.due_at > ?1
  AND co.due_at <= ?2
ORDER BY co.due_at, co.id
"""

ACTIVE_CHILD_IDS = """
SELECT u.id
FROM users AS u
JOIN family_members AS fm ON fm.user_id = u.id
WHERE fm.family_id = ?1
  AND fm.role = 'CHILD'
  AND u.is_active = 1
ORDER BY u.id
"""

MARK_REMINDER_SENT = """
UPDATE chore_occurrences
SET reminder_sent_at = ?1, updated_at = ?1
WHERE id = ?2
  AND family_id = ?3
  AND reminder_sent_at IS NULL
"""


class ChoreRepository:
    def __init__(self, db: Database):
        self.db = db

    async def list_for_child(
        self, family_id: str, child_user_id: str
    ) -> list[dict]:
        return await self.db.many(LIST_FOR_CHILD, family_id, child_user_id)

    async def list_for_parent(self, family_id: str) -> list[dict]:
        return await self.db.many(LIST_FOR_PARENT, family_id)

    async def find_by_id(self, chore_id: str, family_id: str) -> dict | None:
        return await self.db.one(FIND, chore_id, family_id)

    async def create(
        self,
        chore_id: str,
        family_id: str,
        title: str,
        description: str,
        suggested_points: int,
        mode: str,
        assigned_to_user_id: str | None,
        schedule_type: str,
        schedule_frequency: str,
        start_date: str | None,
        due_local_time: str | None,
        weekday_mask: int,
        reminders_enabled: bool,
        created_by_user_id: str,
        now: str,
    ) -> None:
        await self.db.execute(
            CREATE,
            chore_id,
            family_id,
            title,
            description,
            suggested_points,
            mode,
            assigned_to_user_id,
            schedule_type,
            schedule_frequency,
            start_date,
            due_local_time,
            weekday_mask,
            int(reminders_enabled),
            created_by_user_id,
            now,
        )

    def update_statements(
        self,
        chore_id: str,
        family_id: str,
        title: str,
        description: str,
        suggested_points: int,
        mode: str,
        assigned_to_user_id: str | None,
        schedule_type: str,
        schedule_frequency: str,
        start_date: str | None,
        due_local_time: str | None,
        weekday_mask: int,
        reminders_enabled: bool,
        now: str,
    ) -> list[DbStatement]:
        return [
            DbStatement(
                UPDATE,
                (
                    title,
                    description,
                    suggested_points,
                    mode,
                    assigned_to_user_id,
                    schedule_type,
                    schedule_frequency,
                    start_date,
                    due_local_time,
                    weekday_mask,
                    int(reminders_enabled),
                    now,
                    chore_id,
                    family_id,
                ),
            ),
            DbStatement(DELETE_FUTURE_OPEN, (chore_id, family_id, now)),
        ]

    def deactivate_statements(
        self, chore_id: str, family_id: str, now: str
    ) -> list[DbStatement]:
        return [
            DbStatement(DEACTIVATE, (now, chore_id, family_id)),
            DbStatement(CANCEL_OPEN, (now, chore_id, family_id)),
        ]

    def complete_one_time_statement(
        self, chore_id: str, family_id: str, now: str
    ) -> DbStatement:
        return DbStatement(COMPLETE_ONE_TIME, (now, chore_id, family_id))

    def reopen_one_time_statement(
        self, chore_id: str, family_id: str, now: str
    ) -> DbStatement:
        return DbStatement(REOPEN_ONE_TIME, (now, chore_id, family_id))

    async def active_families(self) -> list[dict]:
        return await self.db.many(ACTIVE_FAMILIES)

    async def scheduled_for_family(self, family_id: str) -> list[dict]:
        return await self.db.many(SCHEDULED_FOR_FAMILY, family_id)

    async def create_occurrence(
        self,
        occurrence_id: str,
        chore: dict,
        local_due_date: str,
        due_at: str,
        now: str,
    ) -> int:
        result = await self.db.execute(
            CREATE_OCCURRENCE,
            occurrence_id,
            chore["id"],
            chore["family_id"],
            chore["assigned_to_user_id"],
            chore["title"],
            chore["description"],
            chore["suggested_points"],
            local_due_date,
            due_at,
            now,
        )
        return result.changes

    async def miss_older(
        self, chore_id: str, family_id: str, due_at: str, now: str
    ) -> None:
        await self.db.execute(
            MISS_OLDER, now, chore_id, family_id, due_at
        )

    async def due_occurrences(self, now: str) -> list[dict]:
        return await self.db.many(DUE_OCCURRENCES, now)

    async def mark_overdue(
        self, occurrence_id: str, family_id: str, now: str
    ) -> int:
        result = await self.db.execute(
            MARK_OVERDUE, now, occurrence_id, family_id
        )
        return result.changes

    async def reminders(
        self, now: str, reminder_limit: str
    ) -> list[dict]:
        return await self.db.many(REMINDERS, now, reminder_limit)

    async def active_child_ids(self, family_id: str) -> list[str]:
        return [
            row["id"]
            for row in await self.db.many(ACTIVE_CHILD_IDS, family_id)
        ]

    async def mark_reminder_sent(
        self, occurrence_id: str, family_id: str, now: str
    ) -> int:
        result = await self.db.execute(
            MARK_REMINDER_SENT, now, occurrence_id, family_id
        )
        return result.changes
