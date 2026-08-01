from __future__ import annotations

from collections.abc import Awaitable, Callable

from app.db import Database
from app.errors import Conflict, InvalidRequest, ResourceNotFound
from app.models import ChoreWrite
from app.repositories.children import ChildRepository
from app.repositories.chores import ChoreRepository
from app.realtime_contract import publish_realtime
from app.services.common import new_id, utc_now


Materialize = Callable[[], Awaitable[None]]


class ChoreService:
    def __init__(
        self,
        db: Database,
        env,
        chores: ChoreRepository,
        children: ChildRepository,
        materialize: Materialize | None = None,
    ):
        self.db = db
        self.env = env
        self.chores = chores
        self.children = children
        self.materialize = materialize

    @staticmethod
    def normalized_schedule(
        payload: ChoreWrite,
    ) -> tuple[str | None, str | None]:
        if payload.schedule_type == "NONE":
            return None, None
        if not payload.start_date or not payload.due_local_time:
            raise InvalidRequest(
                "Scheduled chores need a start date and due time"
            )
        return payload.start_date.isoformat(), payload.due_local_time

    @staticmethod
    def stored_schedule(schedule_type: str) -> str:
        if schedule_type in {"NONE", "DAILY"}:
            return schedule_type
        return "WEEKDAYS"

    async def _validate_assignee(
        self, family_id: str, child_user_id: str | None
    ) -> None:
        if child_user_id and not await self.children.find_in_family(
            child_user_id, family_id
        ):
            raise ResourceNotFound("Child profile not found")

    async def list(
        self, family_id: str, user_id: str, role: str
    ) -> list[dict]:
        if role == "CHILD":
            return await self.chores.list_for_child(family_id, user_id)
        return await self.chores.list_for_parent(family_id)

    async def create(
        self,
        family_id: str,
        parent_user_id: str,
        payload: ChoreWrite,
    ) -> dict:
        await self._validate_assignee(
            family_id, payload.assigned_to_user_id
        )
        start_date, due_time = self.normalized_schedule(payload)
        chore_id, now = new_id(), utc_now()
        await self.chores.create(
            chore_id,
            family_id,
            payload.title.strip(),
            payload.description.strip(),
            payload.suggested_points,
            payload.mode,
            payload.assigned_to_user_id,
            self.stored_schedule(payload.schedule_type),
            payload.schedule_type,
            start_date,
            due_time,
            payload.weekday_mask,
            payload.reminders_enabled,
            parent_user_id,
            now,
        )
        if payload.schedule_type != "NONE" and self.materialize:
            await self.materialize()
        await publish_realtime(
            self.env, family_id, "chores.changed", "household"
        )
        return {
            "id": chore_id,
            **payload.model_dump(),
            "state": "ACTIVE",
            "created_at": now,
        }

    async def update(
        self, family_id: str, chore_id: str, payload: ChoreWrite
    ) -> dict:
        existing = await self.chores.find_by_id(chore_id, family_id)
        if not existing:
            raise ResourceNotFound()
        if existing["state"] != "ACTIVE":
            raise Conflict("Only active chores can be edited")
        await self._validate_assignee(
            family_id, payload.assigned_to_user_id
        )
        start_date, due_time = self.normalized_schedule(payload)
        results = await self.db.batch(
            self.chores.update_statements(
                chore_id,
                family_id,
                payload.title.strip(),
                payload.description.strip(),
                payload.suggested_points,
                payload.mode,
                payload.assigned_to_user_id,
                self.stored_schedule(payload.schedule_type),
                payload.schedule_type,
                start_date,
                due_time,
                payload.weekday_mask,
                payload.reminders_enabled,
                utc_now(),
            )
        )
        if not results or results[0].changes != 1:
            raise Conflict("Chore changed while it was being edited")
        if payload.schedule_type != "NONE" and self.materialize:
            await self.materialize()
        await publish_realtime(
            self.env, family_id, "chores.changed", "household"
        )
        return {"id": chore_id, **payload.model_dump(), "state": "ACTIVE"}

    async def deactivate(self, family_id: str, chore_id: str) -> None:
        if not await self.chores.find_by_id(chore_id, family_id):
            raise ResourceNotFound()
        results = await self.db.batch(
            self.chores.deactivate_statements(
                chore_id, family_id, utc_now()
            )
        )
        if not results or results[0].changes != 1:
            raise Conflict("Chore changed while it was being deactivated")
        await publish_realtime(
            self.env, family_id, "chores.changed", "household"
        )
