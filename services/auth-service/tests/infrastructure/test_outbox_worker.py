from datetime import datetime, timezone
from uuid import UUID

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
        return self.pending[:limit]

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

    async def republish(
        self, envelope: EventEnvelope, *, queue: str, attempt: int
    ) -> None:
        pass

    async def publish_dead_letter(
        self, envelope: EventEnvelope, *, reason: str
    ) -> None:
        pass

    async def publish_raw_dead_letter(
        self, body: bytes, *, reason: str
    ) -> None:
        pass

    async def close(self) -> None:
        pass


def _pending(event_type: str = "user.logged_in") -> PendingEvent:
    envelope = EventEnvelope.create(
        type=event_type,
        producer="auth-service",
        payload={"email": "ana@example.com"},
        correlation_id="req-1234",
    )
    return PendingEvent(
        event_id=envelope.event_id, attempts=0, envelope=envelope
    )


async def test_worker_publishes_pending_events_and_marks_them() -> None:
    record = _pending()
    outbox = FakeOutbox([record])
    publisher = FakePublisher()
    worker = OutboxWorker(outbox, publisher)

    processed = await worker.process_once()

    assert processed == 1
    assert publisher.published == [record.envelope]
    assert outbox.published == [record.event_id]
    assert outbox.failed == []


async def test_worker_marks_a_failed_publication_for_retry() -> None:
    failing = _pending()
    healthy = _pending("user.login_failed")
    outbox = FakeOutbox([failing, healthy])
    publisher = FakePublisher(failing={failing.event_id})
    worker = OutboxWorker(
        outbox,
        publisher,
        retry_policy=RetryPolicy(
            max_attempts=5,
            initial_delay_seconds=2,
            multiplier=1,
            max_delay_seconds=2,
        ),
    )

    processed = await worker.process_once()

    assert processed == 2
    assert publisher.published == [healthy.envelope]
    assert outbox.published == [healthy.event_id]
    assert len(outbox.failed) == 1
    failed_id, error, retry_at = outbox.failed[0]
    assert failed_id == failing.event_id
    assert "broker unavailable" in error
    assert retry_at > datetime.now(timezone.utc)
