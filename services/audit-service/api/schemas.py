"""Request and response schemas (Pydantic at the system boundary)."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel

from domain.audit.entity import AuditEntry


class AuditEntryResponse(BaseModel):
    event_id: UUID
    type: str
    version: int
    occurred_at: datetime
    producer: str
    actor_id: str | None
    payload: dict[str, Any]
    correlation_id: str

    @classmethod
    def from_domain(cls, entry: AuditEntry) -> "AuditEntryResponse":
        return cls(
            event_id=entry.event_id,
            type=entry.type.value,
            version=entry.version,
            occurred_at=entry.occurred_at,
            producer=entry.producer,
            actor_id=entry.actor_id.value if entry.actor_id else None,
            payload=entry.payload.value,
            correlation_id=entry.correlation_id,
        )


class AuditPageResponse(BaseModel):
    items: list[AuditEntryResponse]
    total: int
    page: int
    page_size: int
