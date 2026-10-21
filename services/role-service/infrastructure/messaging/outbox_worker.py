"""Background worker that publishes pending outbox events with backoff."""

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Protocol
from uuid import UUID

from app_common.event_consumer import RetryPolicy
from app_common.event_publisher import EventPublisher
from app_common.logging import log_event
from infrastructure.persistence.outbox_store import PendingEvent

logger = logging.getLogger("role.outbox")


class Outbox(Protocol):
    async def pending_batch(self, limit: int) -> list[PendingEvent]: ...

    async def mark_published(self, event_id: UUID) -> None: ...

    async def mark_failed(
        self, event_id: UUID, *, error: str, retry_at: datetime
    ) -> None: ...


class OutboxWorker:
    def __init__(
        self,
        outbox: Outbox,
        publisher: EventPublisher,
        *,
        batch_size: int = 50,
        poll_interval_seconds: float = 1.0,
        retry_policy: RetryPolicy | None = None,
    ) -> None:
        if batch_size < 1:
            raise ValueError("batch_size must be >= 1")
        if poll_interval_seconds <= 0:
            raise ValueError("poll_interval_seconds must be > 0")
        self._outbox = outbox
        self._publisher = publisher
        self._batch_size = batch_size
        self._poll_interval_seconds = poll_interval_seconds
        self._retry_policy = retry_policy or RetryPolicy()

    async def run(self, stop: asyncio.Event) -> None:
        while not stop.is_set():
            try:
                await self.process_once()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("outbox worker iteration failed")
            try:
                await asyncio.wait_for(
                    stop.wait(), timeout=self._poll_interval_seconds
                )
            except TimeoutError:
                pass

    async def process_once(self) -> int:
        pending = await self._outbox.pending_batch(self._batch_size)
        for record in pending:
            try:
                await self._publisher.publish(record.envelope)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                retry_at = datetime.now(timezone.utc) + timedelta(
                    seconds=self._retry_policy.delay_for(record.attempts + 1)
                )
                await self._outbox.mark_failed(
                    record.event_id,
                    error=f"{type(exc).__name__}: {exc}",
                    retry_at=retry_at,
                )
                log_event(
                    logger,
                    logging.WARNING,
                    "outbox publication failed",
                    event_id=str(record.event_id),
                    event_type=record.envelope.type,
                    attempts=record.attempts + 1,
                    retry_at=retry_at.isoformat(),
                    reason=str(exc),
                )
            else:
                await self._outbox.mark_published(record.event_id)
                log_event(
                    logger,
                    logging.INFO,
                    "outbox event published",
                    event_id=str(record.event_id),
                    event_type=record.envelope.type,
                )
        return len(pending)
