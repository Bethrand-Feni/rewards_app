from __future__ import annotations

from typing import Any

from app.db import Database, to_python
from app.errors import (
    Conflict,
    PayloadTooLarge,
    ResourceNotFound,
    UnsupportedMedia,
)
from app.models import RedemptionReview, RewardWrite
from app.repositories.points import PointRepository
from app.repositories.rewards import RewardRepository
from app.realtime_contract import publish_realtime
from app.services.common import new_id, utc_now
from app.services.notification_service import NotificationService


class RewardService:
    MAX_IMAGE_BYTES = 5 * 1024 * 1024
    IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}
    def __init__(
        self,
        db: Database,
        env: Any,
        rewards: RewardRepository,
        points: PointRepository,
        notifications: NotificationService,
    ):
        self.db = db
        self.env = env
        self.rewards = rewards
        self.points = points
        self.notifications = notifications

    async def _reward(self, family_id: str, reward_id: str) -> dict:
        reward = await self.rewards.find_by_id(reward_id, family_id)
        if not reward:
            raise ResourceNotFound()
        return reward

    async def _redemption(
        self, family_id: str, redemption_id: str
    ) -> dict:
        redemption = await self.rewards.find_redemption(
            redemption_id, family_id
        )
        if not redemption:
            raise ResourceNotFound()
        return redemption

    async def list_rewards(self, family_id: str, role: str) -> list[dict]:
        rewards = await self.rewards.list_for_family(
            family_id, child=role == "CHILD"
        )
        return [
            {
                **{key: value for key, value in reward.items() if key != "r2_image_key"},
                "has_image": bool(reward.get("r2_image_key")),
            }
            for reward in rewards
        ]

    @classmethod
    def validate_image(cls, content: bytes, content_type: str) -> str:
        if content_type not in cls.IMAGE_TYPES:
            raise UnsupportedMedia("Use a JPEG, PNG, or WebP image")
        if not content or len(content) > cls.MAX_IMAGE_BYTES:
            raise PayloadTooLarge("Image must be between 1 byte and 5 MB")
        valid = (
            content.startswith(b"\xff\xd8\xff")
            or content.startswith(b"\x89PNG\r\n\x1a\n")
            or (content.startswith(b"RIFF") and content[8:12] == b"WEBP")
        )
        if not valid:
            raise UnsupportedMedia("Image contents do not match a supported format")
        return {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}[content_type]

    async def upload_image(
        self,
        family_id: str,
        reward_id: str,
        content: bytes,
        content_type: str,
    ) -> dict:
        reward = await self._reward(family_id, reward_id)
        extension = self.validate_image(content, content_type)
        object_key = f"families/{family_id}/rewards/{reward_id}/{new_id()}.{extension}"
        await self.env.PHOTOS.put(object_key, content)
        try:
            if await self.rewards.update_image(
                reward_id, family_id, object_key, utc_now()
            ) != 1:
                raise Conflict("Reward changed while its image was uploaded")
        except Exception:
            await self.env.PHOTOS.delete(object_key)
            raise
        previous_key = reward.get("r2_image_key")
        if previous_key and previous_key != object_key:
            await self.env.PHOTOS.delete(previous_key)
        await publish_realtime(
            self.env, family_id, "rewards.changed", "household"
        )
        return {"id": reward_id, "has_image": True}

    async def image(
        self, family_id: str, reward_id: str
    ) -> tuple[bytes, str]:
        reward = await self._reward(family_id, reward_id)
        object_key = reward.get("r2_image_key")
        if not object_key:
            raise ResourceNotFound("Reward image not found")
        stored = await self.env.PHOTOS.get(object_key)
        if stored is None:
            raise ResourceNotFound("Reward image not found")
        extension = object_key.rsplit(".", 1)[-1].casefold()
        content_type = {
            "jpg": "image/jpeg",
            "jpeg": "image/jpeg",
            "png": "image/png",
            "webp": "image/webp",
        }.get(extension, "image/jpeg")
        return bytes(to_python(await stored.arrayBuffer())), content_type

    async def create_reward(
        self,
        family_id: str,
        parent_user_id: str,
        payload: RewardWrite,
    ) -> dict:
        reward_id, now = new_id(), utc_now()
        await self.rewards.create(
            reward_id,
            family_id,
            payload.name.strip(),
            payload.description.strip(),
            payload.point_cost,
            parent_user_id,
            now,
        )
        await publish_realtime(
            self.env, family_id, "rewards.changed", "household"
        )
        return {
            "id": reward_id,
            **payload.model_dump(),
            "is_active": 1,
            "has_image": False,
            "created_at": now,
        }

    async def update_reward(
        self, family_id: str, reward_id: str, payload: RewardWrite
    ) -> dict:
        await self._reward(family_id, reward_id)
        changed = await self.rewards.update(
            reward_id,
            family_id,
            payload.name.strip(),
            payload.description.strip(),
            payload.point_cost,
            utc_now(),
        )
        if changed != 1:
            raise Conflict("Reward changed while it was being edited")
        await publish_realtime(
            self.env, family_id, "rewards.changed", "household"
        )
        return {"id": reward_id, **payload.model_dump()}

    async def deactivate_reward(
        self, family_id: str, reward_id: str
    ) -> None:
        await self._reward(family_id, reward_id)
        if await self.rewards.deactivate(
            reward_id, family_id, utc_now()
        ) != 1:
            raise Conflict("Reward changed while it was being deactivated")
        await publish_realtime(
            self.env, family_id, "rewards.changed", "household"
        )

    async def request_redemption(
        self,
        family_id: str,
        child_user_id: str,
        child_name: str,
        reward_id: str,
    ) -> dict:
        reward = await self._reward(family_id, reward_id)
        if not reward["is_active"]:
            raise Conflict("This reward is no longer available")
        if (
            await self.points.balance(family_id, child_user_id)
            < int(reward["point_cost"])
        ):
            raise Conflict("You do not have enough points")
        redemption_id, now = new_id(), utc_now()
        try:
            await self.rewards.create_redemption(
                redemption_id,
                family_id,
                reward_id,
                child_user_id,
                int(reward["point_cost"]),
                reward["name"],
                now,
            )
        except Exception as exc:
            raise Conflict("You already requested this reward") from exc
        await publish_realtime(
            self.env, family_id, "redemption.created", "parents"
        )
        await self.notifications.enqueue_for_parents(
            family_id,
            "REWARD_REQUESTED",
            "New reward request",
            f"{child_name} requested {reward['name']}.",
            "/parent/reviews",
            redemption_id,
        )
        return {
            "id": redemption_id,
            "status": "PENDING",
            "point_cost_snapshot": reward["point_cost"],
        }

    async def list_mine(
        self, family_id: str, child_user_id: str
    ) -> list[dict]:
        return await self.rewards.list_mine(family_id, child_user_id)

    async def list_pending(self, family_id: str) -> list[dict]:
        return await self.rewards.list_pending(family_id)

    async def approve(
        self,
        family_id: str,
        parent_user_id: str,
        redemption_id: str,
        payload: RedemptionReview,
    ) -> dict:
        redemption = await self._redemption(family_id, redemption_id)
        if redemption["status"] != "PENDING":
            raise Conflict("Request is no longer pending")
        cost = int(redemption["point_cost_snapshot"])
        if (
            await self.points.balance(
                family_id, redemption["child_user_id"]
            )
            < cost
        ):
            raise Conflict("The child no longer has enough points")
        now = utc_now()
        results = await self.db.batch(
            [
                self.points.deduct_for_redemption_statement(
                    new_id(),
                    family_id,
                    parent_user_id,
                    now,
                    redemption_id,
                ),
                self.rewards.approve_statement(
                    redemption_id,
                    family_id,
                    payload.comment.strip(),
                    parent_user_id,
                    now,
                ),
            ]
        )
        if len(results) != 2 or any(result.changes != 1 for result in results):
            raise Conflict("Request could not be approved")
        await publish_realtime(
            self.env,
            family_id,
            "redemption.updated",
            "child",
            redemption["child_user_id"],
        )
        await publish_realtime(
            self.env,
            family_id,
            "points.changed",
            "child",
            redemption["child_user_id"],
        )
        await self.notifications.enqueue(
            family_id,
            redemption["child_user_id"],
            "REWARD_APPROVED",
            "Reward approved",
            "Your reward request was approved.",
            "/child/rewards",
            f"reward-approved:{redemption_id}",
        )
        return {
            "id": redemption_id,
            "status": "APPROVED",
            "points_deducted": cost,
        }

    async def reject(
        self,
        family_id: str,
        parent_user_id: str,
        redemption_id: str,
        payload: RedemptionReview,
    ) -> dict:
        redemption = await self._redemption(family_id, redemption_id)
        if redemption["status"] != "PENDING":
            raise Conflict("Request is no longer pending")
        if (
            await self.rewards.reject(
                redemption_id,
                family_id,
                payload.comment.strip(),
                parent_user_id,
                utc_now(),
            )
            != 1
        ):
            raise Conflict("Request is no longer pending")
        await publish_realtime(
            self.env,
            family_id,
            "redemption.updated",
            "child",
            redemption["child_user_id"],
        )
        await self.notifications.enqueue(
            family_id,
            redemption["child_user_id"],
            "REWARD_REJECTED",
            "Reward request updated",
            "Your reward request was not approved.",
            "/child/rewards",
            f"reward-rejected:{redemption_id}",
        )
        return {"id": redemption_id, "status": "REJECTED"}
