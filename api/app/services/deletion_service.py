from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from app.db import Database
from app.errors import InvalidRequest, ResourceNotFound
from app.models import FamilyDeletionCreate
from app.repositories.deletions import DeletionRepository
from app.realtime_contract import publish_realtime
from app.security import Principal
from app.services.auth_service import AuthService
from app.services.common import new_id, utc_now


class DeletionService:
    def __init__(
        self,
        db: Database,
        env: Any,
        repository: DeletionRepository,
        auth: AuthService,
    ):
        self.db = db
        self.env = env
        self.repository = repository
        self.auth = auth

    async def schedule_family(
        self, principal: Principal, payload: FamilyDeletionCreate
    ) -> dict:
        family_name = await self.repository.family_name(
            principal.family_id
        )
        if payload.family_name.strip() != family_name:
            raise InvalidRequest("Household name does not match")
        await self.auth.confirm_parent(
            principal,
            payload.password,
            payload.google_id_token,
            payload.nonce,
        )
        now = datetime.now(UTC)
        execute_after = (now + timedelta(days=30)).isoformat()
        await self.db.batch(
            self.repository.schedule_family_statements(
                new_id(),
                principal.family_id,
                principal.user_id,
                execute_after,
                now.isoformat(),
            )
        )
        return {"status": "PENDING", "execute_after": execute_after}

    async def cancel_family(self, principal: Principal) -> dict:
        if (
            await self.repository.cancel(
                "FAMILY",
                principal.family_id,
                principal.family_id,
                utc_now(),
            )
            != 1
        ):
            raise ResourceNotFound("No pending household deletion")
        await self.repository.clear_family_schedule(principal.family_id)
        return {"status": "CANCELLED"}

    async def schedule_child(
        self,
        principal: Principal,
        child_id: str,
    ) -> dict:
        child = await self.repository.child(
            child_id, principal.family_id
        )
        if not child:
            raise ResourceNotFound("Child profile not found")
        now = datetime.now(UTC)
        execute_after = (now + timedelta(days=30)).isoformat()
        await self.db.batch(
            self.repository.schedule_child_statements(
                new_id(),
                child_id,
                principal.family_id,
                principal.user_id,
                execute_after,
                now.isoformat(),
            )
        )
        await publish_realtime(
            self.env,
            principal.family_id,
            "children.changed",
            "household",
        )
        return {"status": "PENDING", "execute_after": execute_after}

    async def cancel_child(
        self, principal: Principal, child_id: str
    ) -> dict:
        now = utc_now()
        if (
            await self.repository.cancel(
                "CHILD", child_id, principal.family_id, now
            )
            != 1
        ):
            raise ResourceNotFound("No pending child deletion")
        await self.repository.restore_child(child_id, now)
        await publish_realtime(
            self.env,
            principal.family_id,
            "children.changed",
            "household",
        )
        return {"status": "CANCELLED"}

    async def purge_due(self) -> None:
        for deletion in await self.repository.due(utc_now()):
            try:
                if deletion["target_type"] == "CHILD":
                    keys = await self.repository.child_image_keys(
                        deletion["family_id"], deletion["target_id"]
                    )
                    for key in keys:
                        await self.env.PHOTOS.delete(key)
                    await self.db.batch(
                        self.repository.child_purge_statements(
                            deletion["id"],
                            deletion["family_id"],
                            deletion["target_id"],
                        )
                    )
                else:
                    keys = await self.repository.family_image_keys(
                        deletion["family_id"]
                    )
                    for key in keys:
                        await self.env.PHOTOS.delete(key)
                    user_ids = await self.repository.family_user_ids(
                        deletion["family_id"]
                    )
                    await self.db.batch(
                        self.repository.family_purge_statements(
                            deletion["family_id"], user_ids
                        )
                    )
            except Exception as exc:
                await self.repository.fail(
                    deletion["id"], str(exc)
                )
