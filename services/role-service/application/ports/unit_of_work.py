"""Port for transactions that persist aggregates and their outbox events."""

from types import TracebackType
from typing import Protocol, Self

from application.ports.event_outbox import EventOutbox
from domain.role.repository import AssignmentRepository, RoleRepository


class UnitOfWork(Protocol):
    roles: RoleRepository
    assignments: AssignmentRepository
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
