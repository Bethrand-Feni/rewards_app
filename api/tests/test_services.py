from __future__ import annotations

from dataclasses import dataclass

import pytest

from app.db import ExecuteResult
from app.errors import Conflict, UnsupportedMedia
from app.models import RedemptionReview
from app.services.reward_service import RewardService


class FakeDatabase:
    def __init__(self, results):
        self.results = results
        self.statements = None

    async def batch(self, statements):
        self.statements = statements
        return self.results


class FakeRewards:
    async def find_redemption(self, redemption_id, family_id):
        return {
            "id": redemption_id,
            "family_id": family_id,
            "child_user_id": "child-1",
            "point_cost_snapshot": 40,
            "status": "PENDING",
        }

    def approve_statement(
        self,
        redemption_id,
        family_id,
        comment,
        reviewer_id,
        now,
    ):
        return ("approve", redemption_id, family_id)


class FakePoints:
    async def balance(self, family_id, user_id):
        return 60

    def deduct_for_redemption_statement(
        self,
        transaction_id,
        family_id,
        created_by_user_id,
        now,
        redemption_id,
    ):
        return ("deduct", redemption_id, family_id)


class FakeNotifications:
    def __init__(self):
        self.calls = []

    async def enqueue(self, *args):
        self.calls.append(args)


@dataclass
class FakeEnv:
    pass


@pytest.mark.asyncio
async def test_reward_approval_does_not_notify_after_stale_batch() -> None:
    db = FakeDatabase([ExecuteResult(1), ExecuteResult(0)])
    notifications = FakeNotifications()
    service = RewardService(
        db,
        FakeEnv(),
        FakeRewards(),
        FakePoints(),
        notifications,
    )

    with pytest.raises(Conflict, match="could not be approved"):
        await service.approve(
            "family-1",
            "parent-1",
            "redemption-1",
            RedemptionReview(comment="Approved"),
        )

    assert db.statements[0][0] == "deduct"
    assert db.statements[1][0] == "approve"
    assert notifications.calls == []


def test_reward_image_validation_checks_content_not_only_mime_type() -> None:
    assert RewardService.validate_image(
        b"\x89PNG\r\n\x1a\nimage-data", "image/png"
    ) == "png"
    with pytest.raises(UnsupportedMedia, match="contents"):
        RewardService.validate_image(b"not-an-image", "image/png")
