from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import Any

from app.db import to_python
from app.repositories.chores import ChoreRepository
from app.repositories.notifications import NotificationRepository
from app.scheduling import due_at_utc, local_today, occurrence_dates
from app.services.common import env_value, new_id, utc_now
from app.services.deletion_service import DeletionService
from app.services.notification_service import NotificationService


class SchedulerService:
    def __init__(
        self,
        env: Any,
        chores: ChoreRepository,
        notification_repository: NotificationRepository,
        notifications: NotificationService,
        deletions: DeletionService,
    ):
        self.env = env
        self.chores = chores
        self.notification_repository = notification_repository
        self.notifications = notifications
        self.deletions = deletions

    async def materialize_occurrences(self) -> None:
        now = datetime.now(UTC)
        for family in await self.chores.active_families():
            timezone = family["timezone"] or "Africa/Johannesburg"
            for chore in await self.chores.scheduled_for_family(
                family["id"]
            ):
                start = datetime.fromisoformat(
                    chore["start_date"]
                ).date()
                dates = occurrence_dates(
                    chore.get("schedule_frequency")
                    or (
                        "LEGACY_WEEKDAYS"
                        if chore["schedule_type"] == "WEEKDAYS"
                        else chore["schedule_type"]
                    ),
                    start,
                    int(chore["weekday_mask"]),
                    local_today(now, timezone),
                )
                for local_date in dates:
                    due_at = due_at_utc(
                        local_date, chore["due_local_time"], timezone
                    ).isoformat()
                    created = await self.chores.create_occurrence(
                        new_id(),
                        chore,
                        local_date.isoformat(),
                        due_at,
                        utc_now(),
                    )
                    if created:
                        await self.chores.miss_older(
                            chore["id"],
                            family["id"],
                            due_at,
                            utc_now(),
                        )
        now_iso = utc_now()
        for occurrence in await self.chores.due_occurrences(now_iso):
            if (
                await self.chores.mark_overdue(
                    occurrence["id"], occurrence["family_id"], now_iso
                )
                == 1
            ):
                await self.notifications.enqueue_for_parents(
                    occurrence["family_id"],
                    "CHORE_OVERDUE",
                    "Chore overdue",
                    f"{occurrence['title_snapshot']} is overdue.",
                    "/parent/manage",
                    occurrence["id"],
                )
        reminder_limit = (now + timedelta(hours=1)).isoformat()
        for occurrence in await self.chores.reminders(
            now_iso, reminder_limit
        ):
            recipients = (
                [occurrence["assigned_to_user_id"]]
                if occurrence["assigned_to_user_id"]
                else await self.chores.active_child_ids(
                    occurrence["family_id"]
                )
            )
            for recipient_id in recipients:
                await self.notifications.enqueue(
                    occurrence["family_id"],
                    recipient_id,
                    "CHORE_REMINDER",
                    "Chore due soon",
                    f"{occurrence['title_snapshot']} is due in about an hour.",
                    "/child/chores",
                    f"reminder:{occurrence['id']}:{recipient_id}",
                )
            await self.chores.mark_reminder_sent(
                occurrence["id"], occurrence["family_id"], now_iso
            )

    async def deliver_outbox(self) -> None:
        from workers import fetch as worker_fetch

        for item in await self.notification_repository.pending_outbox(
            utc_now()
        ):
            try:
                response = await worker_fetch(
                    "https://exp.host/--/api/v2/push/send",
                    method="POST",
                    headers={
                        "Accept": "application/json",
                        "Content-Type": "application/json",
                    },
                    body=json.dumps(
                        {
                            "to": item["expo_push_token"],
                            "sound": "default",
                            "title": item["title"],
                            "body": item["body"],
                            "data": {"route": item["route"]},
                        }
                    ),
                )
                payload = to_python(await response.json())
                ticket = (
                    payload.get("data", payload)
                    if isinstance(payload, dict)
                    else {}
                )
                if response.status >= 300 or ticket.get("status") == "error":
                    raise RuntimeError(
                        ticket.get(
                            "message", f"Expo returned {response.status}"
                        )
                    )
                await self.notification_repository.mark_sent(
                    item["id"],
                    item["family_id"],
                    ticket.get("id"),
                    utc_now(),
                )
            except Exception as exc:
                attempts = int(item["attempts"]) + 1
                await self.notification_repository.mark_retry(
                    item["id"],
                    item["family_id"],
                    "FAILED" if attempts >= 5 else "RETRY",
                    attempts,
                    (
                        datetime.now(UTC)
                        + timedelta(minutes=2**attempts)
                    ).isoformat(),
                    str(exc),
                    utc_now(),
                )

    async def check_receipts(self) -> None:
        from workers import fetch as worker_fetch

        sent = await self.notification_repository.sent_for_receipts(
            (datetime.now(UTC) - timedelta(minutes=15)).isoformat()
        )
        if not sent:
            return
        try:
            response = await worker_fetch(
                "https://exp.host/--/api/v2/push/getReceipts",
                method="POST",
                headers={
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                },
                body=json.dumps(
                    {"ids": [item["expo_ticket_id"] for item in sent]}
                ),
            )
            if response.status >= 300:
                return
            payload = to_python(await response.json())
            receipts = (
                payload.get("data", {})
                if isinstance(payload, dict)
                else {}
            )
            for item in sent:
                receipt = receipts.get(item["expo_ticket_id"])
                if not receipt:
                    continue
                if receipt.get("status") == "ok":
                    await self.notification_repository.mark_delivered(
                        item["id"], item["family_id"], utc_now()
                    )
                    continue
                details = receipt.get("details") or {}
                error_code = details.get("error", "UNKNOWN")
                await self.notification_repository.mark_failed(
                    item["id"],
                    item["family_id"],
                    str(receipt.get("message") or error_code),
                    utc_now(),
                )
                if error_code == "DeviceNotRegistered":
                    await self.notification_repository.deactivate_latest_device(
                        item["recipient_user_id"],
                        item["family_id"],
                        utc_now(),
                    )
        except Exception:
            return

    async def run(self) -> None:
        await self.materialize_occurrences()
        await self.deliver_outbox()
        await self.check_receipts()
        if (
            env_value(
                self.env, "DELETION_PURGE_ENABLED", "false"
            ).casefold()
            == "true"
        ):
            await self.deletions.purge_due()
