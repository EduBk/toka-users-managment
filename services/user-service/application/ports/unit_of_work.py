"""Port for transactions that persist the aggregate and its outbox events."""

from types import TracebackType
from typing import Protocol, Self

from application.ports.event_outbox import EventOutbox
from domain.user.repository import UserRepository


class UnitOfWork(Protocol):
    users: UserRepository
    outbox: EventOutbox

    async def __aenter__(self) -> Self: ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None: ...

    async def commit(self) -> None: ...

    async def rollback(self) -> None: ...


class UnitOfWorkFactory(Protocol):
    def __call__(self) -> UnitOfWork: ...
