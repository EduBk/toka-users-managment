"""RabbitMQ publisher for domain events.

Events go to the durable topic exchange ``domain.events`` using the event type
as routing key. Retries and dead letters are routed through the same adapter so
the consumer can reuse one connection.
"""

import asyncio
from contextlib import suppress
from typing import Any, Protocol

import aio_pika
from aio_pika import DeliveryMode, ExchangeType, Message
from aio_pika.abc import AbstractChannel, AbstractExchange

from app_common.event_envelope import EventEnvelope

DOMAIN_EXCHANGE = "domain.events"
DEAD_LETTER_EXCHANGE = "domain.events.dlx"
ATTEMPT_HEADER = "x-attempts"
ERROR_HEADER = "x-error"
_MAX_ERROR_LENGTH = 500


class EventPublisher(Protocol):
    """Broker operations required by the outbox worker and the consumer."""

    async def publish(self, envelope: EventEnvelope) -> None: ...

    async def republish(
        self, envelope: EventEnvelope, *, queue: str, attempt: int
    ) -> None: ...

    async def publish_dead_letter(
        self, envelope: EventEnvelope, *, reason: str
    ) -> None: ...

    async def publish_raw_dead_letter(self, body: bytes, *, reason: str) -> None: ...

    async def close(self) -> None: ...


class RabbitMqEventPublisher:
    """Lazy, reconnecting publisher with broker confirms."""

    def __init__(
        self,
        rabbitmq_url: str,
        *,
        exchange_name: str = DOMAIN_EXCHANGE,
        dead_letter_exchange_name: str = DEAD_LETTER_EXCHANGE,
    ) -> None:
        self._url = rabbitmq_url
        self._exchange_name = exchange_name
        self._dead_letter_exchange_name = dead_letter_exchange_name
        self._connection: aio_pika.abc.AbstractRobustConnection | None = None
        self._channel: AbstractChannel | None = None
        self._exchange: AbstractExchange | None = None
        self._dead_letter_exchange: AbstractExchange | None = None
        self._lock = asyncio.Lock()

    async def _ensure_channel(
        self,
    ) -> tuple[AbstractChannel, AbstractExchange, AbstractExchange]:
        if self._channel is not None and not self._channel.is_closed:
            assert self._exchange is not None
            assert self._dead_letter_exchange is not None
            return self._channel, self._exchange, self._dead_letter_exchange

        async with self._lock:
            if self._channel is not None and not self._channel.is_closed:
                assert self._exchange is not None
                assert self._dead_letter_exchange is not None
                return self._channel, self._exchange, self._dead_letter_exchange

            self._connection = await aio_pika.connect_robust(self._url)
            self._channel = await self._connection.channel(publisher_confirms=True)
            self._exchange = await self._channel.declare_exchange(
                self._exchange_name,
                ExchangeType.TOPIC,
                durable=True,
            )
            self._dead_letter_exchange = await self._channel.declare_exchange(
                self._dead_letter_exchange_name,
                ExchangeType.FANOUT,
                durable=True,
            )
            return self._channel, self._exchange, self._dead_letter_exchange

    async def publish(self, envelope: EventEnvelope) -> None:
        _channel, exchange, _dlx = await self._ensure_channel()
        await exchange.publish(self._message(envelope), routing_key=envelope.type)

    async def republish(
        self, envelope: EventEnvelope, *, queue: str, attempt: int
    ) -> None:
        channel, _exchange, _dlx = await self._ensure_channel()
        await channel.default_exchange.publish(
            self._message(envelope, headers={ATTEMPT_HEADER: attempt}),
            routing_key=queue,
        )

    async def publish_dead_letter(
        self, envelope: EventEnvelope, *, reason: str
    ) -> None:
        _channel, _exchange, dlx = await self._ensure_channel()
        await dlx.publish(
            self._message(
                envelope,
                headers={ERROR_HEADER: reason[:_MAX_ERROR_LENGTH]},
            ),
            routing_key="",
        )

    async def publish_raw_dead_letter(self, body: bytes, *, reason: str) -> None:
        _channel, _exchange, dlx = await self._ensure_channel()
        await dlx.publish(
            Message(
                body=body,
                content_type="application/json",
                delivery_mode=DeliveryMode.PERSISTENT,
                headers={ERROR_HEADER: reason[:_MAX_ERROR_LENGTH]},
            ),
            routing_key="",
        )

    def _message(
        self,
        envelope: EventEnvelope,
        *,
        headers: dict[str, Any] | None = None,
    ) -> Message:
        return Message(
            body=envelope.to_json().encode("utf-8"),
            content_type="application/json",
            delivery_mode=DeliveryMode.PERSISTENT,
            message_id=str(envelope.event_id),
            correlation_id=envelope.correlation_id,
            timestamp=envelope.occurred_at,
            headers=headers,
        )

    async def close(self) -> None:
        with suppress(Exception):
            if self._channel is not None and not self._channel.is_closed:
                await self._channel.close()
        with suppress(Exception):
            if self._connection is not None and not self._connection.is_closed:
                await self._connection.close()
        self._channel = None
        self._connection = None
        self._exchange = None
        self._dead_letter_exchange = None
