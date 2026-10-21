"""Port for durably recording domain events before they reach the broker."""

from typing import Protocol

from domain.auth.events import DomainEvent


class EventOutbox(Protocol):
    async def append(
        self, event: DomainEvent, *, correlation_id: str
    ) -> None: ...
