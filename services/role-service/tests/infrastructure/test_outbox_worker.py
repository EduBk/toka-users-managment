import asyncio
from datetime import datetime, timezone
from uuid import UUID

import pytest

from app_common.event_consumer import RetryPolicy
from app_common.event_envelope import EventEnvelope
from infrastructure.messaging.outbox_worker import OutboxWorker
from infrastructure.persistence.outbox_store import PendingEvent


class FakeOutbox:
    def __init__(self, pending: list[PendingEvent]) -> None:
        self.pending = pending
        self.published: list[UUID] = []
        self.failed: list[tuple[UUID, str, datetime]] = []

    async def pending_batch(self, limit: int) -> list[PendingEvent]:
        batch, self.pending = self.pending[:limit], self.pending[limit:]
        return batch

    async def mark_published(self, event_id: UUID) -> None:
        self.published.append(event_id)

    async def mark_failed(
        self, event_id: UUID, *, error: str, retry_at: datetime
    ) -> None:
        self.failed.append((event_id, error, retry_at))


class FakePublisher:
    def __init__(self, failing: set[UUID] | None = None) -> None:
        self.published: list[EventEnvelope] = []
        self.failing = failing or set()

    async def publish(self, envelope: EventEnvelope) -> None:
        if envelope.event_id in self.failing:
            raise RuntimeError("broker unavailable")
        self.published.append(envelope)


def _pending(event_type: str = "role.assigned") -> PendingEvent:
    envelope = EventEnvelope.create(
        type=event_type,
        producer="role-service",
        payload={"user_id": "u-1"},
        correlation_id="req-1234",
    )
    return PendingEvent(event_id=envelope.event_id, attempts=0, envelope=envelope)


async def test_worker_publishes_pending_events_and_marks_them() -> None:
    record = _pending()
    outbox = FakeOutbox([record])
    publisher = FakePublisher()

    processed = await OutboxWorker(outbox, publisher).process_once()  # type: ignore[arg-type]

    assert processed == 1
    assert publisher.published == [record.envelope]
    assert outbox.published == [record.event_id]


async def test_worker_schedules_a_retry_when_publication_fails() -> None:
    failing = _pending()
    healthy = _pending("role.revoked")
    outbox = FakeOutbox([failing, healthy])
    worker = OutboxWorker(
        outbox,
        FakePublisher(failing={failing.event_id}),  # type: ignore[arg-type]
        retry_policy=RetryPolicy(initial_delay_seconds=2, max_delay_seconds=2),
    )

    await worker.process_once()

    assert outbox.published == [healthy.event_id]
    failed_id, error, retry_at = outbox.failed[0]
    assert failed_id == failing.event_id
    assert "broker unavailable" in error
    assert retry_at > datetime.now(timezone.utc)


async def test_run_drains_the_outbox_until_stopped() -> None:
    outbox = FakeOutbox([_pending()])
    stop = asyncio.Event()
    worker = OutboxWorker(
        outbox, FakePublisher(), poll_interval_seconds=0.01  # type: ignore[arg-type]
    )

    task = asyncio.create_task(worker.run(stop))
    await asyncio.sleep(0.05)
    stop.set()
    await task

    assert len(outbox.published) == 1


@pytest.mark.parametrize(
    ("batch_size", "poll_interval"), [(0, 1.0), (10, 0)]
)
def test_worker_rejects_invalid_settings(
    batch_size: int, poll_interval: float
) -> None:
    with pytest.raises(ValueError):
        OutboxWorker(
            FakeOutbox([]),
            FakePublisher(),  # type: ignore[arg-type]
            batch_size=batch_size,
            poll_interval_seconds=poll_interval,
        )
