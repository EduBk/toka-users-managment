"""Commands, queries and results accepted by the audit use cases."""

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from domain.audit.entity import AuditEntry


@dataclass(frozen=True, slots=True)
class RecordAuditEntryCommand:
    event_id: UUID
    event_type: str
    version: int
    occurred_at: datetime
    producer: str
    payload: dict[str, Any]
    correlation_id: str
    actor_id: str | None


@dataclass(frozen=True, slots=True)
class SearchAuditEntriesQuery:
    user: str | None
    event_type: str | None
    from_at: datetime | None
    to_at: datetime | None
    page: int
    page_size: int


@dataclass(frozen=True, slots=True)
class AuditEntryPage:
    items: list[AuditEntry]
    total: int
    page: int
    page_size: int
