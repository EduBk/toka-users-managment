import asyncio
from collections.abc import Mapping
from typing import Any
from uuid import UUID

import aio_pika
import pytest
from aio_pika.exceptions import AMQPConnectionError

from app_common.event_consumer import (
    EventDeliveryHandler,
    IdempotentEventHandler,
    RabbitMqEventConsumer,
    RetryPolicy,
)
from app_common.event_envelope import EventEnvelope


class FakeDelivery:
    def __init__(
        self,
        body: bytes,
        headers: Mapping[str, Any] | None = None,
    ) -> None:
        self.body = body
        self.headers = headers or {}
        self.acks = 0

    async def ack(self) -> None:
        self.acks += 1


class FakePublisher:
    def __init__(self) -> None:
        self.published: list[EventEnvelope] = []
        self.republished: list[tuple[EventEnvelope, str, int]] = []
        self.dead_letters: list[tuple[EventEnvelope, str]] = []
        self.raw_dead_letters: list[tuple[bytes, str]] = []

    async def publish(self, envelope: EventEnvelope) -> None:
        self.published.append(envelope)

    async def republish(
        self, envelope: EventEnvelope, *, queue: str, attempt: int
    ) -> None:
        self.republished.append((envelope, queue, attempt))

    async def publish_dead_letter(
        self, envelope: EventEnvelope, *, reason: str
    ) -> None:
        self.dead_letters.append((envelope, reason))

    async def publish_raw_dead_letter(
        self, body: bytes, *, reason: str
    ) -> None:
        self.raw_dead_letters.append((body, reason))

    async def close(self) -> None:
        pass


class FakeProcessedStore:
    def __init__(self) -> None:
        self.processed: set[UUID] = set()

    async def is_processed(self, event_id: UUID) -> bool:
        return event_id in self.processed

    async def mark_processed(self, event_id: UUID) -> None:
        self.processed.add(event_id)


class RecordingSleeper:
    def __init__(self) -> None:
        self.delays: list[float] = []

    async def __call__(self, delay: float) -> None:
        self.delays.append(delay)


def _envelope() -> EventEnvelope:
    return EventEnvelope.create(
        type="user.logged_in",
        producer="auth-service",
        payload={"user_id": "u-1", "email": "ana@example.com"},
        correlation_id="req-1234",
    )


async def test_successful_delivery_is_acked_once() -> None:
    handled: list[EventEnvelope] = []

    async def handler(event: EventEnvelope) -> None:
        handled.append(event)

    publisher = FakePublisher()
    event = _envelope()
    delivery = FakeDelivery(event.to_json().encode("utf-8"))
    handler_under_test = EventDeliveryHandler(
        handler, publisher, queue_name="audit-service"
    )

    await handler_under_test.handle(delivery)

    assert handled == [event]
    assert delivery.acks == 1
    assert publisher.republished == []
    assert publisher.dead_letters == []


async def test_failures_retry_with_exponential_backoff_then_dead_letter() -> None:
    async def handler(_event: EventEnvelope) -> None:
        raise RuntimeError("mongo unavailable")

    publisher = FakePublisher()
    sleeper = RecordingSleeper()
    event = _envelope()
    handler_under_test = EventDeliveryHandler(
        handler,
        publisher,
        queue_name="audit-service",
        retry_policy=RetryPolicy(
            max_attempts=3, initial_delay_seconds=1, multiplier=2
        ),
        sleeper=sleeper,
    )
    deliveries = [
        FakeDelivery(event.to_json().encode("utf-8")),
        FakeDelivery(
            event.to_json().encode("utf-8"), headers={"x-attempts": 1}
        ),
        FakeDelivery(
            event.to_json().encode("utf-8"), headers={"x-attempts": 2}
        ),
    ]

    for delivery in deliveries:
        await handler_under_test.handle(delivery)

    assert sleeper.delays == [1, 2]
    assert [attempt for _, _, attempt in publisher.republished] == [1, 2]
    assert [queue for _, queue, _ in publisher.republished] == [
        "audit-service",
        "audit-service",
    ]
    assert len(publisher.dead_letters) == 1
    assert "mongo unavailable" in publisher.dead_letters[0][1]
    assert [delivery.acks for delivery in deliveries] == [1, 1, 1]


async def test_a_retried_delivery_continues_from_its_attempt_header() -> None:
    async def handler(_event: EventEnvelope) -> None:
        raise RuntimeError("still failing")

    publisher = FakePublisher()
    sleeper = RecordingSleeper()
    delivery = FakeDelivery(
        _envelope().to_json().encode("utf-8"),
        headers={"x-attempts": "2"},
    )
    handler_under_test = EventDeliveryHandler(
        handler,
        publisher,
        queue_name="audit-service",
        retry_policy=RetryPolicy(max_attempts=3, initial_delay_seconds=1),
        sleeper=sleeper,
    )

    await handler_under_test.handle(delivery)

    assert publisher.republished == []
    assert len(publisher.dead_letters) == 1
    assert delivery.acks == 1


async def test_unparseable_delivery_goes_to_the_dead_letter_queue() -> None:
    async def handler(_event: EventEnvelope) -> None:
        raise AssertionError("handler must not run")

    publisher = FakePublisher()
    delivery = FakeDelivery(b"not-json")
    handler_under_test = EventDeliveryHandler(
        handler, publisher, queue_name="audit-service"
    )

    await handler_under_test.handle(delivery)

    assert len(publisher.raw_dead_letters) == 1
    assert publisher.raw_dead_letters[0][0] == b"not-json"
    assert delivery.acks == 1


async def test_idempotent_handler_skips_duplicate_event_ids() -> None:
    handled: list[UUID] = []
    store = FakeProcessedStore()

    async def handler(event: EventEnvelope) -> None:
        handled.append(event.event_id)

    idempotent = IdempotentEventHandler(handler, store)
    event = _envelope()

    await idempotent(event)
    await idempotent(event)

    assert handled == [event.event_id]
    assert store.processed == {event.event_id}


def test_retry_policy_caps_the_delay() -> None:
    policy = RetryPolicy(
        max_attempts=5,
        initial_delay_seconds=2,
        multiplier=3,
        max_delay_seconds=10,
    )

    assert policy.delay_for(1) == 2
    assert policy.delay_for(2) == 6
    assert policy.delay_for(3) == 10


class FakeQueue:
    def __init__(self) -> None:
        self.consume_calls = 0

    async def bind(self, _exchange: object, *, routing_key: str) -> None:
        pass

    async def consume(self, _callback: object) -> None:
        self.consume_calls += 1


class FakeChannel:
    def __init__(self) -> None:
        self.queue = FakeQueue()

    async def set_qos(self, *, prefetch_count: int) -> None:
        pass

    async def declare_exchange(
        self, _name: str, _type: object, *, durable: bool
    ) -> object:
        return object()

    async def declare_queue(
        self, _name: str, *, durable: bool, arguments: Mapping[str, Any]
    ) -> FakeQueue:
        return self.queue


class FakeConnection:
    def __init__(self) -> None:
        self.channel_instance = FakeChannel()

    async def channel(self) -> FakeChannel:
        return self.channel_instance


def _consumer(connect_attempts: int) -> RabbitMqEventConsumer:
    async def handler(_event: EventEnvelope) -> None:
        pass

    return RabbitMqEventConsumer(
        "amqp://guest:guest@rabbitmq:5672/",
        "audit-service",
        handler,
        FakePublisher(),
        connect_attempts=connect_attempts,
        connect_retry_delay_seconds=0,
    )


async def test_consumer_retries_transient_broker_connection_failures(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    attempts = 0
    connection = FakeConnection()

    async def fake_connect(_url: str) -> FakeConnection:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise AMQPConnectionError("connection refused")
        return connection

    async def fake_sleep(_delay: float) -> None:
        pass

    monkeypatch.setattr(aio_pika, "connect_robust", fake_connect)
    monkeypatch.setattr(asyncio, "sleep", fake_sleep)

    consumer = _consumer(connect_attempts=2)
    await consumer.start()

    assert attempts == 2
    assert connection.channel_instance.queue.consume_calls == 1


async def test_consumer_gives_up_after_the_configured_connect_attempts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    attempts = 0

    async def fake_connect(_url: str) -> FakeConnection:
        nonlocal attempts
        attempts += 1
        raise AMQPConnectionError("connection refused")

    async def fake_sleep(_delay: float) -> None:
        pass

    monkeypatch.setattr(aio_pika, "connect_robust", fake_connect)
    monkeypatch.setattr(asyncio, "sleep", fake_sleep)

    consumer = _consumer(connect_attempts=2)
    with pytest.raises(AMQPConnectionError):
        await consumer.start()

    assert attempts == 2
