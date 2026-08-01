from __future__ import annotations

from typing import Any


PARENT_EVENTS = {"submission.created", "redemption.created", "children.changed"}
HOUSEHOLD_EVENTS = {"chores.changed", "rewards.changed"}
CHILD_EVENTS = {"submission.updated", "points.changed", "redemption.updated"}
REALTIME_EVENTS = PARENT_EVENTS | HOUSEHOLD_EVENTS | CHILD_EVENTS


def should_deliver(metadata: dict[str, str], event: dict[str, str]) -> bool:
    audience = event.get("audience")
    if audience == "parents":
        return metadata.get("role") == "PARENT"
    if audience == "child":
        return (
            metadata.get("role") == "CHILD"
            and metadata.get("userId") == event.get("targetUserId")
        )
    return audience == "household"


async def publish_realtime(
    env: Any,
    family_id: str,
    event_type: str,
    audience: str,
    target_user_id: str | None = None,
) -> bool:
    """Publish an invalidation hint without affecting the committed business action."""
    import json

    try:
        event = {"type": event_type, "audience": audience}
        if target_user_id:
            event["targetUserId"] = target_user_id
        stub = env.HOUSEHOLD_REALTIME.getByName(f"family:{family_id}")
        response = await stub.fetch(
            "https://realtime.internal/publish",
            method="POST",
            headers={"Content-Type": "application/json"},
            body=json.dumps(event),
        )
        if response.status >= 400:
            raise RuntimeError(f"Durable Object returned {response.status}")
        return True
    except Exception as exc:
        print(f"Realtime publish failed for {event_type}: {exc}")
        return False
