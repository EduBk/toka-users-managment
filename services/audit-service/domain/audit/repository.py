"""Outbound port for audit entry persistence and queries."""

from datetime import datetime
from typing import Protocol
from uuid import UUID

from domain.audit.entity import AuditEntry


class AuditEntryRepository(Protocol):
    async def add_if_absent(self, entry: AuditEntry) -> bool: ...

    async def exists(self, event_id: UUID) -> bool: ...

    async def search(
        self,
        *,
        user: str | None,
        event_type: str | None,
        from_at: datetime | None,
        to_at: datetime | None,
        page: int,
        page_size: int,
    ) -> tuple[list[AuditEntry], int]: ...
