from __future__ import annotations

from app.db import Database, DbStatement


FIND_BY_ID = """
SELECT id, name, access_code, timezone, deletion_scheduled_for, created_at
FROM families
WHERE id = ?1
LIMIT 1
"""

FIND_BY_CODE = """
SELECT id, name, access_code, timezone, deletion_scheduled_for, created_at
FROM families
WHERE access_code = ?1
LIMIT 1
"""

UPDATE_ACCESS_CODE = """
UPDATE families
SET access_code = ?1
WHERE id = ?2
"""

CREATE = """
INSERT INTO families (id, name, access_code, timezone, created_at)
VALUES (?1, ?2, ?3, ?4, ?5)
"""


class FamilyRepository:
    def __init__(self, db: Database):
        self.db = db

    async def find_by_id(self, family_id: str) -> dict | None:
        return await self.db.one(FIND_BY_ID, family_id)

    async def find_by_code(self, access_code: str) -> dict | None:
        return await self.db.one(FIND_BY_CODE, access_code)

    async def update_access_code(self, family_id: str, code: str) -> None:
        await self.db.execute(UPDATE_ACCESS_CODE, code, family_id)

    def create_statement(
        self, family_id: str, name: str, code: str, timezone: str, now: str
    ) -> DbStatement:
        return DbStatement(CREATE, (family_id, name, code, timezone, now))
