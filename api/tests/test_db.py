from __future__ import annotations

import pytest

from app.db import Database, DbStatement


class Meta:
    def __init__(self, changes: int):
        self.meta = {"changes": changes}


class AllResult:
    def __init__(self, rows: list[dict]):
        self.results = rows


class Prepared:
    def __init__(self, binding, sql: str):
        self.binding = binding
        self.sql = sql
        self.params = ()

    def bind(self, *params):
        self.params = params
        return self

    async def first(self):
        self.binding.calls.append(("first", self.sql, self.params))
        return self.binding.first_result

    async def all(self):
        self.binding.calls.append(("all", self.sql, self.params))
        return AllResult(self.binding.many_result)

    async def run(self):
        self.binding.calls.append(("run", self.sql, self.params))
        return Meta(self.binding.changes)


class Binding:
    def __init__(self):
        self.calls = []
        self.first_result = {"id": "one"}
        self.many_result = [{"id": "one"}, {"id": "two"}]
        self.changes = 1

    def prepare(self, sql: str):
        return Prepared(self, sql)

    async def batch(self, prepared):
        self.calls.append(
            (
                "batch",
                [(item.sql, item.params) for item in prepared],
            )
        )
        return [Meta(index + 1) for index, _ in enumerate(prepared)]


@pytest.mark.asyncio
async def test_database_converts_reads_and_execute_metadata() -> None:
    binding = Binding()
    db = Database(binding)

    assert await db.one("SELECT ?1", "one") == {"id": "one"}
    assert await db.many("SELECT ?1", "many") == [
        {"id": "one"},
        {"id": "two"},
    ]
    assert (await db.execute("UPDATE values SET item = ?1", "x")).changes == 1


@pytest.mark.asyncio
async def test_database_prepares_atomic_batch_in_order() -> None:
    binding = Binding()
    db = Database(binding)

    results = await db.batch(
        [
            DbStatement("UPDATE first SET value = ?1", ("a",)),
            DbStatement("UPDATE second SET value = ?1", ("b",)),
        ]
    )

    assert [result.changes for result in results] == [1, 2]
    assert binding.calls[-1] == (
        "batch",
        [
            ("UPDATE first SET value = ?1", ("a",)),
            ("UPDATE second SET value = ?1", ("b",)),
        ],
    )
