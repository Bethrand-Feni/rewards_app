from __future__ import annotations

from typing import Any

from app.db import Database, to_python
from app.errors import (
    Conflict,
    InvalidRequest,
    PayloadTooLarge,
    PermissionDenied,
    ResourceNotFound,
    UnsupportedMedia,
)
from app.repositories.chores import ChoreRepository
from app.repositories.points import PointRepository
from app.repositories.submissions import SubmissionRepository
from app.realtime_contract import publish_realtime
from app.services.common import new_id, utc_now
from app.services.notification_service import NotificationService


MAX_IMAGE_BYTES = 5 * 1024 * 1024
IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}


class SubmissionService:
    def __init__(
        self,
        db: Database,
        env: Any,
        submissions: SubmissionRepository,
        chores: ChoreRepository,
        points: PointRepository,
        notifications: NotificationService,
    ):
        self.db = db
        self.env = env
        self.submissions = submissions
        self.chores = chores
        self.points = points
        self.notifications = notifications

    @staticmethod
    def validate_image(content: bytes, content_type: str) -> None:
        if content_type not in IMAGE_TYPES:
            raise UnsupportedMedia("Use a JPEG, PNG, or WebP image")
        if not content or len(content) > MAX_IMAGE_BYTES:
            raise PayloadTooLarge("Image must be between 1 byte and 5 MB")
        valid = (
            content.startswith(b"\xff\xd8\xff")
            or content.startswith(b"\x89PNG\r\n\x1a\n")
            or (
                content.startswith(b"RIFF")
                and content[8:12] == b"WEBP"
            )
        )
        if not valid:
            raise UnsupportedMedia(
                "Image contents do not match a supported format"
            )

    @staticmethod
    def image_extension(content_type: str) -> str:
        return {
            "image/jpeg": "jpg",
            "image/png": "png",
            "image/webp": "webp",
        }[content_type]

    async def _submission(
        self, family_id: str, submission_id: str
    ) -> dict:
        submission = await self.submissions.find_by_id(
            submission_id, family_id
        )
        if not submission:
            raise ResourceNotFound()
        return submission

    async def create(
        self,
        family_id: str,
        child_user_id: str,
        child_name: str,
        submission_type: str,
        title: str,
        description: str,
        chore_id: str | None,
        occurrence_id: str | None,
        content: bytes,
        content_type: str,
    ) -> dict:
        if submission_type not in {"CHORE", "OTHER_ACTIVITY"}:
            raise InvalidRequest("Invalid submission type")
        if submission_type == "CHORE" and not chore_id:
            raise InvalidRequest("A chore is required")
        if submission_type == "OTHER_ACTIVITY" and len(title.strip()) < 2:
            raise InvalidRequest("Add a title for the activity")
        chore = None
        occurrence = None
        if chore_id:
            chore = await self.chores.find_by_id(chore_id, family_id)
            if not chore:
                raise ResourceNotFound()
            if chore["state"] != "ACTIVE":
                raise Conflict("This chore is not available")
            if (
                chore["assigned_to_user_id"]
                and chore["assigned_to_user_id"] != child_user_id
            ):
                raise PermissionDenied(
                    "This chore is assigned to someone else"
                )
            if chore["schedule_type"] != "NONE":
                if not occurrence_id:
                    raise InvalidRequest(
                        "Select a scheduled chore occurrence"
                    )
                occurrence = await self.submissions.find_occurrence(
                    occurrence_id, chore_id, family_id
                )
                if not occurrence or occurrence["status"] not in {
                    "OPEN",
                    "OVERDUE",
                }:
                    raise Conflict("This chore occurrence is unavailable")
                if (
                    occurrence["assigned_to_user_id"]
                    and occurrence["assigned_to_user_id"] != child_user_id
                ):
                    raise PermissionDenied(
                        "This occurrence is assigned to someone else"
                    )
            if await self.submissions.has_active(
                family_id, occurrence_id, child_user_id, chore_id
            ):
                raise Conflict("You already have an active submission")
        self.validate_image(content, content_type)
        submission_id, image_id, now = new_id(), new_id(), utc_now()
        object_key = (
            f"families/{family_id}/submissions/{submission_id}/"
            f"{image_id}.{self.image_extension(content_type)}"
        )
        await self.env.PHOTOS.put(object_key, content)
        actual_title = (
            occurrence["title_snapshot"]
            if occurrence
            else chore["title"]
            if chore
            else title.strip()
        )
        try:
            results = await self.db.batch(
                self.submissions.create_statements(
                    submission_id,
                    image_id,
                    family_id,
                    child_user_id,
                    chore_id,
                    occurrence_id,
                    submission_type,
                    actual_title,
                    description.strip(),
                    bool(chore and chore["mode"] == "ONE_TIME"),
                    object_key,
                    content_type,
                    len(content),
                    now,
                )
            )
            if any(result.changes != 1 for result in results):
                raise Conflict("The chore changed while it was submitted")
        except Exception:
            await self.env.PHOTOS.delete(object_key)
            raise
        await publish_realtime(
            self.env, family_id, "submission.created", "parents"
        )
        if chore and chore["mode"] == "ONE_TIME":
            await publish_realtime(
                self.env, family_id, "chores.changed", "household"
            )
        await self.notifications.enqueue_for_parents(
            family_id,
            "SUBMISSION_CREATED",
            "Chore ready to review",
            f"{child_name} submitted {actual_title}.",
            "/parent/reviews",
            submission_id,
        )
        return {"id": submission_id, "status": "PENDING", "created_at": now}

    async def list_mine(
        self, family_id: str, child_user_id: str
    ) -> list[dict]:
        return await self.submissions.list_mine(family_id, child_user_id)

    async def list_pending(self, family_id: str) -> list[dict]:
        return await self.submissions.list_pending(family_id)

    async def image(
        self,
        family_id: str,
        user_id: str,
        role: str,
        submission_id: str,
    ) -> tuple[bytes, str]:
        submission = await self._submission(family_id, submission_id)
        if role == "CHILD" and submission["child_user_id"] != user_id:
            raise PermissionDenied(
                "This image belongs to another profile"
            )
        image = await self.submissions.current_image(
            submission_id, family_id
        )
        if not image:
            raise ResourceNotFound("Image not found")
        stored = await self.env.PHOTOS.get(image["r2_object_key"])
        if not stored:
            raise ResourceNotFound("Image not found")
        return bytes(to_python(await stored.arrayBuffer())), image["content_type"]

    async def resubmit(
        self,
        family_id: str,
        child_user_id: str,
        child_name: str,
        submission_id: str,
        description: str,
        content: bytes,
        content_type: str,
    ) -> dict:
        submission = await self._submission(family_id, submission_id)
        if submission["child_user_id"] != child_user_id:
            raise PermissionDenied(
                "This submission belongs to another profile"
            )
        if submission["status"] != "CHANGES_REQUESTED":
            raise Conflict("This submission cannot be resubmitted")
        self.validate_image(content, content_type)
        revision = int(submission["current_revision"]) + 1
        image_id, now = new_id(), utc_now()
        object_key = (
            f"families/{family_id}/submissions/{submission_id}/"
            f"{image_id}.{self.image_extension(content_type)}"
        )
        await self.env.PHOTOS.put(object_key, content)
        try:
            results = await self.db.batch(
                self.submissions.resubmit_statements(
                    image_id,
                    submission_id,
                    family_id,
                    child_user_id,
                    revision,
                    object_key,
                    content_type,
                    len(content),
                    description.strip() or submission["description"],
                    now,
                )
            )
            if len(results) != 2 or any(
                result.changes != 1 for result in results
            ):
                raise Conflict("This submission cannot be resubmitted")
        except Exception:
            await self.env.PHOTOS.delete(object_key)
            raise
        await publish_realtime(
            self.env, family_id, "submission.created", "parents"
        )
        await self.notifications.enqueue_for_parents(
            family_id,
            "SUBMISSION_RESUBMITTED",
            "Updated chore proof",
            f"{child_name} updated {submission['title']} for review.",
            "/parent/reviews",
            f"resubmission:{submission_id}:{revision}",
        )
        return {
            "id": submission_id,
            "status": "PENDING",
            "current_revision": revision,
        }

    async def approve(
        self,
        family_id: str,
        parent_user_id: str,
        submission_id: str,
        awarded_points: int,
    ) -> dict:
        submission = await self._submission(family_id, submission_id)
        if submission["status"] != "PENDING":
            raise Conflict("Submission is no longer pending")
        now = utc_now()
        statements = [
            self.submissions.approve_statement(
                submission_id,
                family_id,
                awarded_points,
                parent_user_id,
                now,
            ),
            self.points.award_statement(
                new_id(),
                family_id,
                submission["child_user_id"],
                awarded_points,
                submission_id,
                f"Approved: {submission['title']}",
                parent_user_id,
                now,
            ),
        ]
        if submission["chore_id"]:
            chore = await self.chores.find_by_id(
                submission["chore_id"], family_id
            )
            if chore and chore["mode"] == "ONE_TIME":
                statements.append(
                    self.chores.complete_one_time_statement(
                        submission["chore_id"], family_id, now
                    )
                )
        if submission["chore_occurrence_id"]:
            statements.append(
                self.submissions.complete_occurrence_statement(
                    submission["chore_occurrence_id"], family_id, now
                )
            )
        results = await self.db.batch(statements)
        if len(results) < 2 or results[0].changes != 1 or results[1].changes != 1:
            raise Conflict("Submission could not be approved")
        await publish_realtime(
            self.env,
            family_id,
            "submission.updated",
            "child",
            submission["child_user_id"],
        )
        await publish_realtime(
            self.env,
            family_id,
            "points.changed",
            "child",
            submission["child_user_id"],
        )
        if submission["chore_id"]:
            await publish_realtime(
                self.env, family_id, "chores.changed", "household"
            )
        await self.notifications.enqueue(
            family_id,
            submission["child_user_id"],
            "SUBMISSION_APPROVED",
            "Chore approved",
            f"You earned {awarded_points} points for {submission['title']}.",
            "/child/activity",
            f"submission-approved:{submission_id}",
        )
        return {
            "id": submission_id,
            "status": "APPROVED",
            "awarded_points": awarded_points,
        }

    async def finish_review(
        self,
        family_id: str,
        parent_user_id: str,
        submission_id: str,
        status: str,
        comment: str,
    ) -> dict:
        submission = await self._submission(family_id, submission_id)
        if submission["status"] != "PENDING":
            raise Conflict("Submission is no longer pending")
        now = utc_now()
        statements = [
            self.submissions.finish_review_statement(
                submission_id,
                family_id,
                status,
                comment.strip(),
                parent_user_id,
                now,
            )
        ]
        if status == "REJECTED" and submission["chore_id"]:
            statements.append(
                self.chores.reopen_one_time_statement(
                    submission["chore_id"], family_id, now
                )
            )
        if status == "REJECTED" and submission["chore_occurrence_id"]:
            statements.append(
                self.submissions.reopen_occurrence_statement(
                    submission["chore_occurrence_id"], family_id, now
                )
            )
        results = await self.db.batch(statements)
        if not results or results[0].changes != 1:
            raise Conflict("Submission is no longer pending")
        await publish_realtime(
            self.env,
            family_id,
            "submission.updated",
            "child",
            submission["child_user_id"],
        )
        if submission["chore_id"]:
            await publish_realtime(
                self.env, family_id, "chores.changed", "household"
            )
        await self.notifications.enqueue(
            family_id,
            submission["child_user_id"],
            f"SUBMISSION_{status}",
            "Chore review updated",
            (
                f"Changes were requested for {submission['title']}."
                if status == "CHANGES_REQUESTED"
                else f"{submission['title']} was not approved."
            ),
            "/child/activity",
            f"submission-{status.casefold()}:{submission_id}",
        )
        return {
            "id": submission_id,
            "status": status,
            "review_comment": comment.strip(),
        }
