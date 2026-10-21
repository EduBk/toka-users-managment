"""Outbox persistence.

Two adapters share the ``outbox_events`` table:

- :class:`SqlAlchemyOutboxStore` appends an event using the transaction of the
  unit of work, so the aggregate change and the event commit atomically.
- :class:`SqlAlchemyOutbox` is the worker-facing reader that fetches pending
  events and records publication results.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app_common.event_envelope import EventEnvelope
from domain.user.events import DomainEvent
from infrastructure.persistence.models import OutboxEventModel

_MAX_ERROR_LENGTH = 2000


class SqlAlchemyOutboxStore:
    def __init__(self, session: AsyncSession, *, producer: str) -> None:
        self._session = session
        self._producer = producer

    async def append(
        self, event: DomainEvent, *, correlation_id: str
    ) -> None:
        envelope = EventEnvelope.create(
            type=event.event_type,
            version=event.version,
            producer=self._producer,
            payload=event.payload(),
            correlation_id=correlation_id,
        )
        self._session.add(
            OutboxEventModel(
                event_id=envelope.event_id,
                type=envelope.type,
                version=envelope.version,
                occurred_at=envelope.occurred_at,
                producer=envelope.producer,
                payload=envelope.payload,
                correlation_id=envelope.correlation_id,
            )
        )
        await self._session.flush()


@dataclass(frozen=True, slots=True)
class PendingEvent:
    event_id: UUID
    attempts: int
    envelope: EventEnvelope


class SqlAlchemyOutbox:
    def __init__(
        self, session_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        self._session_factory = session_factory

    async def pending_batch(self, limit: int) -> list[PendingEvent]:
        now = datetime.now(timezone.utc)
        async with self._session_factory() as session:
            rows = (
                await session.scalars(
                    select(OutboxEventModel)
                    .where(
                        OutboxEventModel.published_at.is_(None),
                        OutboxEventModel.next_attempt_at <= now,
                    )
                    .order_by(
                        OutboxEventModel.occurred_at,
                        OutboxEventModel.event_id,
                    )
                    .limit(limit)
                )
            ).all()
        return [_to_pending(row) for row in rows]

    async def mark_published(self, event_id: UUID) -> None:
        async with self._session_factory() as session:
            await session.execute(
                update(OutboxEventModel)
                .where(OutboxEventModel.event_id == event_id)
                .values(
                    published_at=datetime.now(timezone.utc),
                    last_error=None,
                )
            )
            await session.commit()

    async def mark_failed(
        self, event_id: UUID, *, error: str, retry_at: datetime
    ) -> None:
        async with self._session_factory() as session:
            await session.execute(
                update(OutboxEventModel)
                .where(OutboxEventModel.event_id == event_id)
                .values(
                    attempts=OutboxEventModel.attempts + 1,
                    next_attempt_at=retry_at,
                    last_error=error[:_MAX_ERROR_LENGTH],
                )
            )
            await session.commit()


def _to_pending(model: OutboxEventModel) -> PendingEvent:
    return PendingEvent(
        event_id=model.event_id,
        attempts=model.attempts,
        envelope=EventEnvelope(
            event_id=model.event_id,
            type=model.type,
            version=model.version,
            occurred_at=model.occurred_at,
            producer=model.producer,
            payload=model.payload,
            correlation_id=model.correlation_id,
        ),
    )
