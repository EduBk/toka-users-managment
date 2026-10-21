"""Audit entry aggregate root."""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from domain.audit.exceptions import InvalidAuditEntry
from domain.audit.value_objects import ActorId, EventPayload, EventType


@dataclass(frozen=True, slots=True)
class AuditEntry:
    """Immutable record of a domain event received from the broker."""

    event_id: UUID
    type: EventType
    version: int
    occurred_at: datetime
    producer: str
    actor_id: ActorId | None
    payload: EventPayload
    correlation_id: str

    @classmethod
    def create(
        cls,
        *,
        event_id: UUID,
        event_type: str,
        version: int,
        occurred_at: datetime,
        producer: str,
        payload: dict[str, Any],
        correlation_id: str,
        actor_id: str | None = None,
    ) -> "AuditEntry":
        if version < 1:
            raise InvalidAuditEntry("event version must be >= 1")
        if occurred_at.tzinfo is None:
            raise InvalidAuditEntry("occurred_at must include timezone information")

        normalized_producer = producer.strip()
        normalized_correlation = correlation_id.strip()
        if not normalized_producer:
            raise InvalidAuditEntry("event producer is required")
        if not normalized_correlation:
            raise InvalidAuditEntry("correlation_id is required")

        return cls(
            event_id=event_id,
            type=EventType(event_type),
            version=version,
            occurred_at=occurred_at.astimezone(timezone.utc),
            producer=normalized_producer,
            actor_id=ActorId(actor_id) if actor_id else None,
            payload=EventPayload(payload),
            correlation_id=normalized_correlation,
        )
