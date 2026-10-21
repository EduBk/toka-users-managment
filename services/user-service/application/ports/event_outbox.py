"""Port for durably recording domain events in the same transaction."""

from typing import Protocol

from domain.user.events import DomainEvent


class EventOutbox(Protocol):
    async def append(
        self, event: DomainEvent, *, correlation_id: str
    ) -> None: ...
