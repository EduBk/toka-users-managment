"""Port for appending domain events to the transactional outbox."""

from typing import Protocol

from domain.role.events import DomainEvent


class EventOutbox(Protocol):
    async def append(
        self, event: DomainEvent, *, correlation_id: str
    ) -> None: ...
