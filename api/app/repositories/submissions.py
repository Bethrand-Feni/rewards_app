from __future__ import annotations

from app.db import Database, DbStatement


FIND = """
SELECT
  id, family_id, child_user_id, chore_id, chore_occurrence_id,
  submission_type, title, description, status, locks_chore,
  current_revision, awarded_points, review_comment, reviewed_by_user_id,
  reviewed_at, created_at, updated_at
FROM submissions
WHERE id = ?1
  AND family_id = ?2
LIMIT 1
"""

FIND_OCCURRENCE = """
SELECT
  id, chore_id, family_id, assigned_to_user_id, title_snapshot,
  description_snapshot, points_snapshot, local_due_date, due_at, status,
  reminder_sent_at, overdue_notified_at, created_at, updated_at
FROM chore_occurrences
WHERE id = ?1
  AND chore_id = ?2
  AND family_id = ?3
LIMIT 1
"""

FIND_ACTIVE = """
SELECT id
FROM submissions
WHERE family_id = ?1
  AND (
    (?2 IS NOT NULL AND chore_occurrence_id = ?2)
    OR (
      ?2 IS NULL
      AND child_user_id = ?3
      AND chore_id = ?4
    )
  )
  AND status IN ('PENDING', 'CHANGES_REQUESTED')
LIMIT 1
"""

CREATE = """
INSERT INTO submissions (
  id, family_id, child_user_id, chore_id, chore_occurrence_id,
  submission_type, title, description, status, locks_chore,
  created_at, updated_at
) VALUES (
  ?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8, 'PENDING', ?9, ?10, ?10
)
"""

CREATE_IMAGE = """
INSERT INTO submission_images (
  id, submission_id, revision, r2_object_key, content_type, file_size,
  created_at
) VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7)
"""

LOCK_CHORE = """
UPDATE chores
SET state = 'LOCKED', updated_at = ?1
WHERE id = ?2
  AND family_id = ?3
  AND state = 'ACTIVE'
"""

SUBMIT_OCCURRENCE = """
UPDATE chore_occurrences
SET status = 'SUBMITTED', updated_at = ?1
WHERE id = ?2
  AND family_id = ?3
  AND status IN ('OPEN', 'OVERDUE')
"""

SUBMISSION_SELECT = """
SELECT
  s.id, s.family_id, s.child_user_id, s.chore_id,
  s.chore_occurrence_id, s.submission_type, s.title, s.description,
  s.status, s.locks_chore, s.current_revision, s.awarded_points,
  s.review_comment, s.reviewed_by_user_id, s.reviewed_at,
  s.created_at, s.updated_at,
  u.display_name AS child_name,
  c.suggested_points,
  c.mode AS chore_mode,
  si.id AS image_id
FROM submissions AS s
JOIN users AS u ON u.id = s.child_user_id
LEFT JOIN chores AS c
  ON c.id = s.chore_id
 AND c.family_id = s.family_id
LEFT JOIN submission_images AS si
  ON si.submission_id = s.id
 AND si.revision = s.current_revision
"""

MINE = SUBMISSION_SELECT + """
WHERE s.family_id = ?1
  AND s.child_user_id = ?2
ORDER BY s.created_at DESC, s.id DESC
LIMIT 50
"""

PENDING = SUBMISSION_SELECT + """
WHERE s.family_id = ?1
  AND s.status = 'PENDING'
ORDER BY s.created_at, s.id
"""

CURRENT_IMAGE = """
SELECT si.r2_object_key, si.content_type
FROM submission_images AS si
JOIN submissions AS s ON s.id = si.submission_id
WHERE si.submission_id = ?1
  AND s.family_id = ?2
  AND si.revision = s.current_revision
LIMIT 1
"""

RESUBMIT = """
UPDATE submissions
SET status = 'PENDING', current_revision = ?1, description = ?2,
    review_comment = NULL, reviewed_by_user_id = NULL, reviewed_at = NULL,
    updated_at = ?3
WHERE id = ?4
  AND family_id = ?5
  AND child_user_id = ?6
  AND status = 'CHANGES_REQUESTED'
"""

APPROVE = """
UPDATE submissions
SET status = 'APPROVED', awarded_points = ?1, reviewed_by_user_id = ?2,
    reviewed_at = ?3, updated_at = ?3
WHERE id = ?4
  AND family_id = ?5
  AND status = 'PENDING'
"""

FINISH_REVIEW = """
UPDATE submissions
SET status = ?1, review_comment = ?2, reviewed_by_user_id = ?3,
    reviewed_at = ?4, updated_at = ?4
WHERE id = ?5
  AND family_id = ?6
  AND status = 'PENDING'
"""

COMPLETE_OCCURRENCE = """
UPDATE chore_occurrences
SET status = 'COMPLETED', updated_at = ?1
WHERE id = ?2
  AND family_id = ?3
  AND status = 'SUBMITTED'
"""

REOPEN_OCCURRENCE = """
UPDATE chore_occurrences
SET status = 'OPEN', updated_at = ?1
WHERE id = ?2
  AND family_id = ?3
  AND status = 'SUBMITTED'
"""


class SubmissionRepository:
    def __init__(self, db: Database):
        self.db = db

    async def find_by_id(
        self, submission_id: str, family_id: str
    ) -> dict | None:
        return await self.db.one(FIND, submission_id, family_id)

    async def find_occurrence(
        self, occurrence_id: str, chore_id: str, family_id: str
    ) -> dict | None:
        return await self.db.one(
            FIND_OCCURRENCE, occurrence_id, chore_id, family_id
        )

    async def has_active(
        self,
        family_id: str,
        occurrence_id: str | None,
        child_user_id: str,
        chore_id: str,
    ) -> bool:
        return (
            await self.db.one(
                FIND_ACTIVE,
                family_id,
                occurrence_id,
                child_user_id,
                chore_id,
            )
            is not None
        )

    def create_statements(
        self,
        submission_id: str,
        image_id: str,
        family_id: str,
        child_user_id: str,
        chore_id: str | None,
        occurrence_id: str | None,
        submission_type: str,
        title: str,
        description: str,
        locks_chore: bool,
        object_key: str,
        content_type: str,
        file_size: int,
        now: str,
    ) -> list[DbStatement]:
        statements = [
            DbStatement(
                CREATE,
                (
                    submission_id,
                    family_id,
                    child_user_id,
                    chore_id,
                    occurrence_id,
                    submission_type,
                    title,
                    description,
                    int(locks_chore),
                    now,
                ),
            ),
            DbStatement(
                CREATE_IMAGE,
                (
                    image_id,
                    submission_id,
                    1,
                    object_key,
                    content_type,
                    file_size,
                    now,
                ),
            ),
        ]
        if locks_chore and chore_id:
            statements.append(
                DbStatement(LOCK_CHORE, (now, chore_id, family_id))
            )
        if occurrence_id:
            statements.append(
                DbStatement(
                    SUBMIT_OCCURRENCE,
                    (now, occurrence_id, family_id),
                )
            )
        return statements

    async def list_mine(
        self, family_id: str, child_user_id: str
    ) -> list[dict]:
        return await self.db.many(MINE, family_id, child_user_id)

    async def list_pending(self, family_id: str) -> list[dict]:
        return await self.db.many(PENDING, family_id)

    async def current_image(
        self, submission_id: str, family_id: str
    ) -> dict | None:
        return await self.db.one(CURRENT_IMAGE, submission_id, family_id)

    def resubmit_statements(
        self,
        image_id: str,
        submission_id: str,
        family_id: str,
        child_user_id: str,
        revision: int,
        object_key: str,
        content_type: str,
        file_size: int,
        description: str,
        now: str,
    ) -> list[DbStatement]:
        return [
            DbStatement(
                CREATE_IMAGE,
                (
                    image_id,
                    submission_id,
                    revision,
                    object_key,
                    content_type,
                    file_size,
                    now,
                ),
            ),
            DbStatement(
                RESUBMIT,
                (
                    revision,
                    description,
                    now,
                    submission_id,
                    family_id,
                    child_user_id,
                ),
            ),
        ]

    def approve_statement(
        self,
        submission_id: str,
        family_id: str,
        awarded_points: int,
        reviewer_id: str,
        now: str,
    ) -> DbStatement:
        return DbStatement(
            APPROVE,
            (
                awarded_points,
                reviewer_id,
                now,
                submission_id,
                family_id,
            ),
        )

    def finish_review_statement(
        self,
        submission_id: str,
        family_id: str,
        status: str,
        comment: str,
        reviewer_id: str,
        now: str,
    ) -> DbStatement:
        return DbStatement(
            FINISH_REVIEW,
            (
                status,
                comment,
                reviewer_id,
                now,
                submission_id,
                family_id,
            ),
        )

    def complete_occurrence_statement(
        self, occurrence_id: str, family_id: str, now: str
    ) -> DbStatement:
        return DbStatement(
            COMPLETE_OCCURRENCE, (now, occurrence_id, family_id)
        )

    def reopen_occurrence_statement(
        self, occurrence_id: str, family_id: str, now: str
    ) -> DbStatement:
        return DbStatement(REOPEN_OCCURRENCE, (now, occurrence_id, family_id))
