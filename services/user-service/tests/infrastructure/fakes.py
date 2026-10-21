"""Fake Redis and SQLAlchemy session implementations used by the adapter tests."""

from typing import Any

from redis.exceptions import ConnectionError

_UNREACHABLE = "connection refused"


class _ScalarResult:
    def __init__(self, rows: list[Any]) -> None:
        self._rows = rows

    def all(self) -> list[Any]:
        return self._rows


class FakeSession:
    """Records the calls an adapter makes on an ``AsyncSession``."""

    def __init__(
        self,
        *,
        rows: list[Any] | None = None,
        scalar_value: Any = None,
        flush_error: Exception | None = None,
    ) -> None:
        self.rows = rows or []
        self.scalar_value = scalar_value
        self.flush_error = flush_error
        self.added: list[Any] = []
        self.merged: list[Any] = []
        self.executed: list[Any] = []
        self.flushes = 0
        self.commits = 0
        self.rollbacks = 0
        self.closed = False

    async def __aenter__(self) -> "FakeSession":
        return self

    async def __aexit__(self, *_exc_info: object) -> None:
        await self.close()

    def add(self, instance: Any) -> None:
        self.added.append(instance)

    async def merge(self, instance: Any) -> Any:
        self.merged.append(instance)
        return instance

    async def flush(self) -> None:
        if self.flush_error is not None:
            raise self.flush_error
        self.flushes += 1

    async def get(self, _model: type, key: Any) -> Any:
        return next((row for row in self.rows if row.id == key), None)

    async def scalar(self, _statement: Any) -> Any:
        return self.scalar_value

    async def scalars(self, _statement: Any) -> _ScalarResult:
        return _ScalarResult(self.rows)

    async def execute(self, statement: Any) -> None:
        self.executed.append(statement)

    async def commit(self) -> None:
        self.commits += 1

    async def rollback(self) -> None:
        self.rollbacks += 1

    async def close(self) -> None:
        self.closed = True


class FakeRedis:
    def __init__(self) -> None:
        self.data: dict[str, str] = {}
        self.ttls: dict[str, int | None] = {}

    async def get(self, key: str) -> str | None:
        return self.data.get(key)

    async def set(
        self, key: str, value: str, *, ex: int | None = None
    ) -> bool:
        self.data[key] = value
        self.ttls[key] = ex
        return True

    async def delete(self, *keys: str) -> int:
        removed = 0
        for key in keys:
            removed += 1 if self.data.pop(key, None) is not None else 0
        return removed

    async def incr(self, key: str) -> int:
        value = int(self.data.get(key, "0")) + 1
        self.data[key] = str(value)
        return value

    async def exists(self, key: str) -> int:
        return 1 if key in self.data else 0


class FailingRedis:
    """Simulates an unreachable Redis server."""

    async def get(self, key: str) -> str | None:
        raise ConnectionError(_UNREACHABLE)

    async def set(
        self, key: str, value: str, *, ex: int | None = None
    ) -> bool:
        raise ConnectionError(_UNREACHABLE)

    async def delete(self, *keys: str) -> int:
        raise ConnectionError(_UNREACHABLE)

    async def incr(self, key: str) -> int:
        raise ConnectionError(_UNREACHABLE)

    async def exists(self, key: str) -> int:
        raise ConnectionError(_UNREACHABLE)
