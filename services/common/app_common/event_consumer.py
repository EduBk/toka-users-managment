"""Reliable event consumption: manual ack, backoff retries, DLQ and dedupe."""

import asyncio
import logging
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from typing import Any, Protocol
from uuid import UUID

import aio_pika
from aio_pika import ExchangeType
from aio_pika.abc import AbstractChannel, AbstractIncomingMessage, AbstractQueue

from app_common.event_envelope import EventEnvelope
from app_common.event_publisher import EventPublisher
from app_common.logging import log_event

logger = logging.getLogger("app_common.events")

EventHandler = Callable[[EventEnvelope], Awaitable[None]]
Sleeper = Callable[[float], Awaitable[None]]


class EventDelivery(Protocol):
    @property
    def body(self) -> bytes: ...

    @property
    def headers(self) -> Mapping[str, Any]: ...

    async def ack(self) -> None: ...


@dataclass(frozen=True, slots=True)
class RetryPolicy:
    max_attempts: int = 5
    initial_delay_seconds: float = 1.0
    multiplier: float = 2.0
    max_delay_seconds: float = 30.0

    def __post_init__(self) -> None:
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be >= 1")
        if self.initial_delay_seconds < 0:
            raise ValueError("initial_delay_seconds must be >= 0")
        if self.multiplier < 1:
            raise ValueError("multiplier must be >= 1")
        if self.max_delay_seconds < self.initial_delay_seconds:
            raise ValueError("max_delay_seconds must be >= initial_delay_seconds")

    def delay_for(self, attempt: int) -> float:
        if attempt < 1:
            raise ValueError("attempt must be >= 1")
        return min(
            self.initial_delay_seconds * (self.multiplier ** (attempt - 1)),
            self.max_delay_seconds,
        )


class ProcessedEventStore(Protocol):
    """Durable record of the events a consumer has already handled."""

    async def is_processed(self, event_id: UUID) -> bool: ...

    async def mark_processed(self, event_id: UUID) -> None: ...


class IdempotentEventHandler:
    """Skips events whose ``event_id`` was already processed.

    The store must keep a unique constraint on ``event_id``: consumers run with
    at-least-once delivery, so two concurrent deliveries can pass the read
    check before either writes.
    """

    def __init__(
        self, handler: EventHandler, processed: ProcessedEventStore
    ) -> None:
        self._handler = handler
        self._processed = processed

    async def __call__(self, event: EventEnvelope) -> None:
        if await self._processed.is_processed(event.event_id):
            log_event(
                logger,
                logging.INFO,
                "event already processed",
                event_id=str(event.event_id),
                event_type=event.type,
            )
            return
        await self._handler(event)
        await self._processed.mark_processed(event.event_id)


class EventDeliveryHandler:
    """Handles one delivery: retries with backoff, then dead-letters it."""

    def __init__(
        self,
        handler: EventHandler,
        publisher: EventPublisher,
        *,
        queue_name: str,
        retry_policy: RetryPolicy | None = None,
        sleeper: Sleeper = asyncio.sleep,
    ) -> None:
        self._handler = handler
        self._publisher = publisher
        self._queue_name = queue_name
        self._retry_policy = retry_policy or RetryPolicy()
        self._sleep = sleeper

    async def handle(self, delivery: EventDelivery) -> None:
        try:
            event = EventEnvelope.from_json(delivery.body)
        except ValueError as exc:
            await self._publisher.publish_raw_dead_letter(
                delivery.body, reason=f"invalid envelope: {exc}"
            )
            await delivery.ack()
            log_event(
                logger,
                logging.ERROR,
                "unparseable event sent to dead-letter queue",
                reason=str(exc),
            )
            return

        attempts = _delivery_attempts(delivery.headers)
        try:
            await self._handler(event)
        except Exception as exc:
            await self._retry_or_dead_letter(event, delivery, attempts, exc)
        else:
            await delivery.ack()

    async def _retry_or_dead_letter(
        self,
        event: EventEnvelope,
        delivery: EventDelivery,
        attempts: int,
        error: Exception,
    ) -> None:
        next_attempt = attempts + 1
        reason = f"{type(error).__name__}: {error}"

        if next_attempt >= self._retry_policy.max_attempts:
            await self._publisher.publish_dead_letter(event, reason=reason)
            await delivery.ack()
            log_event(
                logger,
                logging.ERROR,
                "event sent to dead-letter queue",
                event_id=str(event.event_id),
                event_type=event.type,
                attempts=next_attempt,
                reason=reason,
            )
            return

        delay = self._retry_policy.delay_for(next_attempt)
        await self._sleep(delay)
        await self._publisher.republish(
            event, queue=self._queue_name, attempt=next_attempt
        )
        await delivery.ack()
        log_event(
            logger,
            logging.WARNING,
            "event scheduled for retry",
            event_id=str(event.event_id),
            event_type=event.type,
            attempt=next_attempt,
            delay_seconds=delay,
            reason=reason,
        )


class RabbitMqEventConsumer:
    """Consumes a durable queue and delegates each delivery to the handler."""

    def __init__(
        self,
        rabbitmq_url: str,
        queue_name: str,
        handler: EventHandler,
        publisher: EventPublisher,
        *,
        prefetch_count: int = 10,
        retry_policy: RetryPolicy | None = None,
        exchange_name: str = "domain.events",
        routing_key: str = "#",
        connect_attempts: int = 10,
        connect_retry_delay_seconds: float = 2.0,
    ) -> None:
        if connect_attempts < 1:
            raise ValueError("connect_attempts must be >= 1")
        if connect_retry_delay_seconds < 0:
            raise ValueError("connect_retry_delay_seconds must be >= 0")
        self._url = rabbitmq_url
        self._queue_name = queue_name
        self._handler = EventDeliveryHandler(
            handler,
            publisher,
            queue_name=queue_name,
            retry_policy=retry_policy,
        )
        self._prefetch_count = prefetch_count
        self._exchange_name = exchange_name
        self._routing_key = routing_key
        self._connect_attempts = connect_attempts
        self._connect_retry_delay_seconds = connect_retry_delay_seconds
        self._connection: aio_pika.abc.AbstractRobustConnection | None = None
        self._channel: AbstractChannel | None = None
        self._queue: AbstractQueue | None = None

    async def start(self) -> None:
        self._connection = await self._connect()
        self._channel = await self._connection.channel()
        await self._channel.set_qos(prefetch_count=self._prefetch_count)
        exchange = await self._channel.declare_exchange(
            self._exchange_name, ExchangeType.TOPIC, durable=True
        )
        self._queue = await self._channel.declare_queue(
            self._queue_name,
            durable=True,
            arguments={"x-dead-letter-exchange": "domain.events.dlx"},
        )
        await self._queue.bind(exchange, routing_key=self._routing_key)
        await self._queue.consume(self._on_message)

    async def _connect(self) -> aio_pika.abc.AbstractRobustConnection:
        attempt = 0
        while True:
            attempt += 1
            try:
                return await aio_pika.connect_robust(self._url)
            except aio_pika.exceptions.AMQPConnectionError as exc:
                if attempt >= self._connect_attempts:
                    raise
                log_event(
                    logger,
                    logging.WARNING,
                    "broker connection failed, retrying",
                    attempt=attempt,
                    max_attempts=self._connect_attempts,
                    delay_seconds=self._connect_retry_delay_seconds,
                    reason=str(exc),
                )
                await asyncio.sleep(self._connect_retry_delay_seconds)

    async def _on_message(self, message: AbstractIncomingMessage) -> None:
        try:
            await self._handler.handle(_AioPikaDelivery(message))
        except Exception:
            logger.exception("event delivery failed before ack")
            await message.nack(requeue=True)

    async def stop(self) -> None:
        if self._channel is not None and not self._channel.is_closed:
            await self._channel.close()
        if self._connection is not None and not self._connection.is_closed:
            await self._connection.close()


class _AioPikaDelivery:
    def __init__(self, message: AbstractIncomingMessage) -> None:
        self._message = message

    @property
    def body(self) -> bytes:
        return self._message.body

    @property
    def headers(self) -> Mapping[str, Any]:
        return self._message.headers or {}

    async def ack(self) -> None:
        await self._message.ack()


def _delivery_attempts(headers: Mapping[str, Any]) -> int:
    try:
        return max(int(headers.get("x-attempts", 0) or 0), 0)
    except (TypeError, ValueError):
        return 0
