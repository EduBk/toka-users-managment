"""Fake SQLAlchemy session used by the adapter tests."""

from typing import Any


class _Result:
    def __init__(self, rows: list[Any], rowcount: int = 0) -> None:
        self._rows = rows
        self.rowcount = rowcount

    def all(self) -> list[Any]:
        return self._rows


class FakeSession:
    """Records the calls an adapter makes on an ``AsyncSession``.

    ``scalars`` and ``scalar`` answer from FIFO queues so multi-query adapters
    can be scripted in order.
    """

    def __init__(
        self,
        *,
        models: list[Any] | None = None,
        scalars: list[list[Any]] | None = None,
        scalar: list[Any] | None = None,
        execute_rows: list[Any] | None = None,
        rowcount: int = 0,
        flush_error: Exception | None = None,
    ) -> None:
        self.models = models or []
        self._scalars = scalars or []
        self._scalar = scalar or []
        self.execute_rows = execute_rows or []
        self.rowcount = rowcount
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

    def add_all(self, instances: list[Any]) -> None:
        self.added.extend(instances)

    async def merge(self, instance: Any) -> Any:
        self.merged.append(instance)
        return instance

    async def flush(self) -> None:
        if self.flush_error is not None:
            raise self.flush_error
        self.flushes += 1

    async def get(self, _model: type, key: Any) -> Any:
        return next((model for model in self.models if model.id == key), None)

    async def scalar(self, _statement: Any) -> Any:
        return self._scalar.pop(0) if self._scalar else None

    async def scalars(self, _statement: Any) -> _Result:
        return _Result(self._scalars.pop(0) if self._scalars else [])

    async def execute(self, statement: Any) -> _Result:
        self.executed.append(statement)
        return _Result(self.execute_rows, self.rowcount)

    async def commit(self) -> None:
        self.commits += 1

    async def rollback(self) -> None:
        self.rollbacks += 1

    async def close(self) -> None:
        self.closed = True
