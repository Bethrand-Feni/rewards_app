from __future__ import annotations

from app.db import Database
from app.repositories.notifications import NotificationRepository
from app.services.common import new_id, utc_now


class NotificationService:
    def __init__(self, db: Database, repository: NotificationRepository):
        self.db = db
        self.repository = repository

    async def enqueue(
        self,
        family_id: str,
        recipient_user_id: str,
        notification_type: str,
        title: str,
        body: str,
        route: str,
        idempotency_key: str,
    ) -> None:
        statement = self.repository.enqueue_statement(
            new_id(),
            family_id,
            recipient_user_id,
            notification_type,
            title,
            body,
            route,
            idempotency_key,
            utc_now(),
        )
        await self.db.batch([statement])

    async def enqueue_for_parents(
        self,
        family_id: str,
        notification_type: str,
        title: str,
        body: str,
        route: str,
        event_id: str,
    ) -> None:
        now = utc_now()
        statements = [
            self.repository.enqueue_statement(
                new_id(),
                family_id,
                parent_id,
                notification_type,
                title,
                body,
                route,
                f"{notification_type}:{event_id}:{parent_id}",
                now,
            )
            for parent_id in await self.repository.parent_ids(family_id)
        ]
        if statements:
            await self.db.batch(statements)

    async def register_device(
        self,
        user_id: str,
        family_id: str,
        installation_id: str,
        expo_push_token: str,
        platform: str,
    ) -> dict:
        await self.repository.upsert_device(
            new_id(),
            user_id,
            family_id,
            installation_id,
            expo_push_token,
            platform,
            utc_now(),
        )
        return {"installation_id": installation_id, "registered": True}

    async def unregister_device(
        self, user_id: str, family_id: str, installation_id: str
    ) -> None:
        await self.repository.deactivate_device(
            user_id, family_id, installation_id, utc_now()
        )
