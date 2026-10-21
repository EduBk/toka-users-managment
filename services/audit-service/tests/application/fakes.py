"""In-memory double for the audit repository."""

from datetime import datetime
from uuid import UUID

from domain.audit.entity import AuditEntry


class InMemoryAuditEntryRepository:
    def __init__(self) -> None:
        self.entries: list[AuditEntry] = []

    async def add_if_absent(self, entry: AuditEntry) -> bool:
        if await self.exists(entry.event_id):
            return False
        self.entries.append(entry)
        return True

    async def exists(self, event_id: UUID) -> bool:
        return any(entry.event_id == event_id for entry in self.entries)

    async def search(
        self,
        *,
        user: str | None,
        event_type: str | None,
        from_at: datetime | None,
        to_at: datetime | None,
        page: int,
        page_size: int,
    ) -> tuple[list[AuditEntry], int]:
        matches = [
            entry
            for entry in self.entries
            if (user is None or (
                entry.actor_id is not None and entry.actor_id.value == user
            ))
            and (event_type is None or entry.type.value == event_type)
            and (from_at is None or entry.occurred_at >= from_at)
            and (to_at is None or entry.occurred_at <= to_at)
        ]
        matches.sort(
            key=lambda entry: (entry.occurred_at, str(entry.event_id)),
            reverse=True,
        )
        start = (page - 1) * page_size
        return matches[start : start + page_size], len(matches)
