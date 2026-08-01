from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable


def to_python(value: Any) -> Any:
    """Convert a Workers JavaScript proxy to an ordinary Python value."""
    if hasattr(value, "to_py"):
        return value.to_py()
    return value


@dataclass(frozen=True)
class DbStatement:
    sql: str
    params: tuple[Any, ...] = ()


@dataclass(frozen=True)
class ExecuteResult:
    changes: int


class Database:
    """Small D1 adapter; application code never touches the binding directly."""

    def __init__(self, binding: Any):
        self._binding = binding

    def prepare(self, statement: DbStatement) -> Any:
        return self._binding.prepare(statement.sql).bind(*statement.params)

    async def one(self, sql: str, *params: Any) -> dict[str, Any] | None:
        value = await self._binding.prepare(sql).bind(*params).first()
        converted = to_python(value)
        return dict(converted) if converted else None

    async def many(self, sql: str, *params: Any) -> list[dict[str, Any]]:
        result = await self._binding.prepare(sql).bind(*params).all()
        return [dict(item) for item in list(to_python(result.results))]

    async def execute(self, sql: str, *params: Any) -> ExecuteResult:
        result = await self._binding.prepare(sql).bind(*params).run()
        metadata = to_python(result.meta)
        return ExecuteResult(changes=int(metadata.get("changes", 0)))

    async def batch(
        self, statements: Iterable[DbStatement]
    ) -> list[ExecuteResult]:
        prepared = [self.prepare(statement) for statement in statements]
        raw_results = list(to_python(await self._binding.batch(prepared)))
        results: list[ExecuteResult] = []
        for result in raw_results:
            metadata = to_python(getattr(result, "meta", {}))
            results.append(ExecuteResult(changes=int(metadata.get("changes", 0))))
        return results
