from __future__ import annotations

from app.db import Database, DbStatement


PARENT_IDS = """
SELECT u.id
FROM users AS u
JOIN family_members AS fm ON fm.user_id = u.id
WHERE fm.family_id = ?1
  AND fm.role = 'PARENT'
  AND u.is_active = 1
ORDER BY u.id
"""

ENQUEUE = """
INSERT OR IGNORE INTO notification_outbox (
  id, family_id, recipient_user_id, notification_type, title, body, route,
  idempotency_key, next_attempt_at, created_at, updated_at
) VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8, ?9, ?9, ?9)
"""

UPSERT_DEVICE = """
INSERT INTO push_devices (
  id, user_id, family_id, installation_id, expo_push_token, platform,
  is_active, created_at, updated_at
) VALUES (?1, ?2, ?3, ?4, ?5, ?6, 1, ?7, ?7)
ON CONFLICT(user_id, installation_id) DO UPDATE SET
  expo_push_token = excluded.expo_push_token,
  platform = excluded.platform,
  family_id = excluded.family_id,
  is_active = 1,
  updated_at = excluded.updated_at
"""

DEACTIVATE_DEVICE = """
UPDATE push_devices
SET is_active = 0, updated_at = ?1
WHERE user_id = ?2
  AND family_id = ?3
  AND installation_id = ?4
"""

PENDING_OUTBOX = """
SELECT
  o.id, o.family_id, o.recipient_user_id, o.notification_type,
  o.title, o.body, o.route, o.idempotency_key, o.status,
  o.expo_ticket_id, o.attempts, o.next_attempt_at, o.sent_at,
  o.delivered_at, o.last_error, o.created_at, o.updated_at,
  d.expo_push_token
FROM notification_outbox AS o
JOIN push_devices AS d
  ON d.user_id = o.recipient_user_id
 AND d.family_id = o.family_id
 AND d.is_active = 1
 AND d.updated_at = (
   SELECT MAX(d2.updated_at)
   FROM push_devices AS d2
   WHERE d2.user_id = o.recipient_user_id
     AND d2.family_id = o.family_id
     AND d2.is_active = 1
 )
WHERE o.status IN ('PENDING', 'RETRY')
  AND o.next_attempt_at <= ?1
ORDER BY o.created_at, o.id
LIMIT 100
"""

MARK_SENT = """
UPDATE notification_outbox
SET status = 'SENT', expo_ticket_id = ?1, attempts = attempts + 1,
    sent_at = ?2, updated_at = ?2
WHERE id = ?3
  AND family_id = ?4
  AND status IN ('PENDING', 'RETRY')
"""

MARK_RETRY = """
UPDATE notification_outbox
SET status = ?1, attempts = ?2, next_attempt_at = ?3,
    last_error = ?4, updated_at = ?5
WHERE id = ?6
  AND family_id = ?7
  AND status IN ('PENDING', 'RETRY')
"""

SENT_FOR_RECEIPTS = """
SELECT
  id, family_id, recipient_user_id, expo_ticket_id, sent_at
FROM notification_outbox
WHERE status = 'SENT'
  AND expo_ticket_id IS NOT NULL
  AND sent_at <= ?1
ORDER BY sent_at, id
LIMIT 300
"""

MARK_DELIVERED = """
UPDATE notification_outbox
SET status = 'DELIVERED', delivered_at = ?1, updated_at = ?1
WHERE id = ?2
  AND family_id = ?3
  AND status = 'SENT'
"""

MARK_FAILED = """
UPDATE notification_outbox
SET status = 'FAILED', last_error = ?1, updated_at = ?2
WHERE id = ?3
  AND family_id = ?4
"""

DEACTIVATE_LATEST_DEVICE = """
UPDATE push_devices
SET is_active = 0, updated_at = ?1
WHERE user_id = ?2
  AND family_id = ?3
  AND updated_at = (
    SELECT MAX(updated_at)
    FROM push_devices
    WHERE user_id = ?2
      AND family_id = ?3
      AND is_active = 1
  )
"""


class NotificationRepository:
    def __init__(self, db: Database):
        self.db = db

    async def parent_ids(self, family_id: str) -> list[str]:
        return [row["id"] for row in await self.db.many(PARENT_IDS, family_id)]

    def enqueue_statement(
        self,
        notification_id: str,
        family_id: str,
        recipient_user_id: str,
        notification_type: str,
        title: str,
        body: str,
        route: str,
        idempotency_key: str,
        now: str,
    ) -> DbStatement:
        return DbStatement(
            ENQUEUE,
            (
                notification_id,
                family_id,
                recipient_user_id,
                notification_type,
                title,
                body,
                route,
                idempotency_key,
                now,
            ),
        )

    async def upsert_device(
        self,
        device_id: str,
        user_id: str,
        family_id: str,
        installation_id: str,
        expo_push_token: str,
        platform: str,
        now: str,
    ) -> None:
        await self.db.execute(
            UPSERT_DEVICE,
            device_id,
            user_id,
            family_id,
            installation_id,
            expo_push_token,
            platform,
            now,
        )

    async def deactivate_device(
        self, user_id: str, family_id: str, installation_id: str, now: str
    ) -> None:
        await self.db.execute(
            DEACTIVATE_DEVICE, now, user_id, family_id, installation_id
        )

    async def pending_outbox(self, now: str) -> list[dict]:
        return await self.db.many(PENDING_OUTBOX, now)

    async def mark_sent(
        self, item_id: str, family_id: str, ticket_id: str | None, now: str
    ) -> None:
        await self.db.execute(
            MARK_SENT, ticket_id, now, item_id, family_id
        )

    async def mark_retry(
        self,
        item_id: str,
        family_id: str,
        status: str,
        attempts: int,
        retry_at: str,
        error: str,
        now: str,
    ) -> None:
        await self.db.execute(
            MARK_RETRY,
            status,
            attempts,
            retry_at,
            error[:500],
            now,
            item_id,
            family_id,
        )

    async def sent_for_receipts(self, cutoff: str) -> list[dict]:
        return await self.db.many(SENT_FOR_RECEIPTS, cutoff)

    async def mark_delivered(
        self, item_id: str, family_id: str, now: str
    ) -> None:
        await self.db.execute(
            MARK_DELIVERED, now, item_id, family_id
        )

    async def mark_failed(
        self, item_id: str, family_id: str, error: str, now: str
    ) -> None:
        await self.db.execute(
            MARK_FAILED, error[:500], now, item_id, family_id
        )

    async def deactivate_latest_device(
        self, user_id: str, family_id: str, now: str
    ) -> None:
        await self.db.execute(
            DEACTIVATE_LATEST_DEVICE, now, user_id, family_id
        )
