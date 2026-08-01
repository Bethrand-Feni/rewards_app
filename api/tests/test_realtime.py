import pytest

from app.realtime_contract import publish_realtime, should_deliver


def test_parent_events_only_reach_parents():
    event = {"type": "submission.created", "audience": "parents"}
    assert should_deliver({"role": "PARENT", "userId": "parent"}, event)
    assert not should_deliver({"role": "CHILD", "userId": "child-a"}, event)


def test_child_events_only_reach_the_target_child():
    event = {
        "type": "submission.updated",
        "audience": "child",
        "targetUserId": "child-a",
    }
    assert should_deliver({"role": "CHILD", "userId": "child-a"}, event)
    assert not should_deliver({"role": "CHILD", "userId": "child-b"}, event)
    assert not should_deliver({"role": "PARENT", "userId": "parent"}, event)


def test_household_events_reach_verified_household_connections():
    event = {"type": "chores.changed", "audience": "household"}
    assert should_deliver({"role": "PARENT", "userId": "parent"}, event)
    assert should_deliver({"role": "CHILD", "userId": "child"}, event)


@pytest.mark.asyncio
async def test_publish_failure_does_not_escape():
    class BrokenNamespace:
        def getByName(self, name):
            raise RuntimeError("realtime unavailable")

    class Env:
        HOUSEHOLD_REALTIME = BrokenNamespace()

    assert not await publish_realtime(
        Env(), "family-a", "submission.created", "parents"
    )


@pytest.mark.asyncio
async def test_publish_uses_the_verified_family_room_and_target():
    class Response:
        status = 204

    class Stub:
        async def fetch(self, url, **options):
            self.url = url
            self.options = options
            return Response()

    class Namespace:
        def __init__(self):
            self.stub = Stub()
            self.room = ""

        def getByName(self, name):
            self.room = name
            return self.stub

    class Env:
        HOUSEHOLD_REALTIME = Namespace()

    env = Env()
    assert await publish_realtime(
        env, "family-a", "points.changed", "child", "child-a"
    )
    assert env.HOUSEHOLD_REALTIME.room == "family:family-a"
    assert '"targetUserId": "child-a"' in env.HOUSEHOLD_REALTIME.stub.options["body"]
