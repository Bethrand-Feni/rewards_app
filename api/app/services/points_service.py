from __future__ import annotations

from typing import Any

from app.errors import Conflict, InvalidRequest
from app.models import AdjustmentCreate
from app.repositories.children import ChildRepository
from app.repositories.points import PointRepository
from app.realtime_contract import publish_realtime
from app.services.common import new_id, utc_now
from app.services.notification_service import NotificationService


class PointsService:
    def __init__(
        self,
        env: Any,
        points: PointRepository,
        children: ChildRepository,
        notifications: NotificationService,
    ):
        self.env = env
        self.points = points
        self.children = children
        self.notifications = notifications

    async def _target(
        self,
        family_id: str,
        user_id: str,
        role: str,
        child_user_id: str | None,
    ) -> str:
        if role == "CHILD":
            return user_id
        if not child_user_id:
            raise InvalidRequest("Select a child profile")
        if not await self.children.find_in_family(child_user_id, family_id):
            from app.errors import ResourceNotFound

            raise ResourceNotFound("Child profile not found")
        return child_user_id

    async def balance(
        self,
        family_id: str,
        user_id: str,
        role: str,
        child_user_id: str | None,
    ) -> dict:
        target = await self._target(
            family_id, user_id, role, child_user_id
        )
        return {
            "user_id": target,
            "balance": await self.points.balance(family_id, target),
        }

    async def history(
        self,
        family_id: str,
        user_id: str,
        role: str,
        child_user_id: str | None,
    ) -> list[dict]:
        target = await self._target(
            family_id, user_id, role, child_user_id
        )
        return await self.points.history(family_id, target)

    async def adjust(
        self,
        family_id: str,
        parent_user_id: str,
        payload: AdjustmentCreate,
    ) -> dict:
        if payload.amount == 0:
            raise InvalidRequest("Adjustment cannot be zero")
        if not await self.children.find_in_family(
            payload.child_user_id, family_id
        ):
            from app.errors import ResourceNotFound

            raise ResourceNotFound("Child profile not found")
        balance = await self.points.balance(family_id, payload.child_user_id)
        if balance + payload.amount < 0:
            raise Conflict("Adjustment would make the balance negative")
        transaction_id, now = new_id(), utc_now()
        await self.points.create_adjustment(
            transaction_id,
            family_id,
            payload.child_user_id,
            payload.amount,
            payload.reason.strip(),
            parent_user_id,
            now,
        )
        await publish_realtime(
            self.env,
            family_id,
            "points.changed",
            "child",
            payload.child_user_id,
        )
        await self.notifications.enqueue(
            family_id,
            payload.child_user_id,
            "POINTS_ADJUSTED",
            "Points updated",
            f"Your balance changed by {payload.amount:+d} points.",
            "/child/activity",
            f"points-adjusted:{transaction_id}",
        )
        return {"id": transaction_id, **payload.model_dump(), "created_at": now}
