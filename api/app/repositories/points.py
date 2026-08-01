from __future__ import annotations

from app.db import Database, DbStatement


BALANCE = """
SELECT COALESCE(SUM(amount), 0) AS balance
FROM point_transactions
WHERE family_id = ?1
  AND user_id = ?2
"""

HISTORY = """
SELECT id, transaction_type, amount, reason, created_at
FROM point_transactions
WHERE family_id = ?1
  AND user_id = ?2
ORDER BY created_at DESC, id DESC
LIMIT 50
"""

CREATE_ADJUSTMENT = """
INSERT INTO point_transactions (
  id, family_id, user_id, transaction_type, amount, reason,
  created_by_user_id, created_at
) VALUES (?1, ?2, ?3, 'MANUAL_ADJUSTMENT', ?4, ?5, ?6, ?7)
"""

AWARD = """
INSERT INTO point_transactions (
  id, family_id, user_id, transaction_type, amount, submission_id,
  reason, created_by_user_id, created_at
) VALUES (?1, ?2, ?3, 'SUBMISSION_REWARD', ?4, ?5, ?6, ?7, ?8)
"""

DEDUCT_FOR_REDEMPTION = """
INSERT INTO point_transactions (
  id, family_id, user_id, transaction_type, amount, redemption_id,
  reason, created_by_user_id, created_at
)
SELECT
  ?1, ?2, rr.child_user_id, 'REWARD_REDEMPTION',
  -rr.point_cost_snapshot, rr.id, 'Reward redeemed', ?3, ?4
FROM reward_redemptions AS rr
WHERE rr.id = ?5
  AND rr.family_id = ?2
  AND rr.status = 'PENDING'
  AND (
    SELECT COALESCE(SUM(pt.amount), 0)
    FROM point_transactions AS pt
    WHERE pt.family_id = ?2
      AND pt.user_id = rr.child_user_id
  ) >= rr.point_cost_snapshot
"""


class PointRepository:
    def __init__(self, db: Database):
        self.db = db

    async def balance(self, family_id: str, user_id: str) -> int:
        row = await self.db.one(BALANCE, family_id, user_id)
        return int(row["balance"]) if row else 0

    async def history(self, family_id: str, user_id: str) -> list[dict]:
        return await self.db.many(HISTORY, family_id, user_id)

    async def create_adjustment(
        self,
        transaction_id: str,
        family_id: str,
        user_id: str,
        amount: int,
        reason: str,
        created_by_user_id: str,
        now: str,
    ) -> None:
        await self.db.execute(
            CREATE_ADJUSTMENT,
            transaction_id,
            family_id,
            user_id,
            amount,
            reason,
            created_by_user_id,
            now,
        )

    def award_statement(
        self,
        transaction_id: str,
        family_id: str,
        user_id: str,
        amount: int,
        submission_id: str,
        reason: str,
        created_by_user_id: str,
        now: str,
    ) -> DbStatement:
        return DbStatement(
            AWARD,
            (
                transaction_id,
                family_id,
                user_id,
                amount,
                submission_id,
                reason,
                created_by_user_id,
                now,
            ),
        )

    def deduct_for_redemption_statement(
        self,
        transaction_id: str,
        family_id: str,
        created_by_user_id: str,
        now: str,
        redemption_id: str,
    ) -> DbStatement:
        return DbStatement(
            DEDUCT_FOR_REDEMPTION,
            (
                transaction_id,
                family_id,
                created_by_user_id,
                now,
                redemption_id,
            ),
        )
