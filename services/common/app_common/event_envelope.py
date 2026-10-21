"""Versioned JSON envelope shared by every domain event."""

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

_REQUIRED_FIELDS = (
    "event_id",
    "type",
    "version",
    "occurred_at",
    "producer",
    "payload",
    "correlation_id",
)


@dataclass(frozen=True, slots=True)
class EventEnvelope:
    """Envelope published to the ``domain.events`` exchange.

    ``event_id`` is the end-to-end idempotency key: producers generate it once
    per business fact and consumers use it to discard duplicates.
    """

    event_id: UUID
    type: str
    version: int
    occurred_at: datetime
    producer: str
    payload: dict[str, Any]
    correlation_id: str

    @classmethod
    def create(
        cls,
        *,
        type: str,
        producer: str,
        payload: dict[str, Any],
        correlation_id: str,
        version: int = 1,
        event_id: UUID | None = None,
        occurred_at: datetime | None = None,
    ) -> "EventEnvelope":
        if not type.strip():
            raise ValueError("event type is required")
        if not producer.strip():
            raise ValueError("event producer is required")
        if version < 1:
            raise ValueError("event version must be >= 1")
        if not isinstance(payload, dict):
            raise ValueError("event payload must be an object")
        return cls(
            event_id=event_id or uuid4(),
            type=type,
            version=version,
            occurred_at=occurred_at or datetime.now(timezone.utc),
            producer=producer,
            payload=payload,
            correlation_id=correlation_id,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": str(self.event_id),
            "type": self.type,
            "version": self.version,
            "occurred_at": self.occurred_at.astimezone(timezone.utc)
            .isoformat()
            .replace("+00:00", "Z"),
            "producer": self.producer,
            "payload": self.payload,
            "correlation_id": self.correlation_id,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, separators=(",", ":"))

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "EventEnvelope":
        missing = [field for field in _REQUIRED_FIELDS if field not in data]
        if missing:
            raise ValueError(f"missing envelope fields: {', '.join(missing)}")

        payload = data["payload"]
        if not isinstance(payload, dict):
            raise ValueError("event payload must be an object")

        try:
            event_id = UUID(str(data["event_id"]))
            version = int(data["version"])
            occurred_at = datetime.fromisoformat(
                str(data["occurred_at"]).replace("Z", "+00:00")
            )
        except (TypeError, ValueError) as exc:
            raise ValueError("invalid event envelope") from exc

        if version < 1:
            raise ValueError("event version must be >= 1")
        if occurred_at.tzinfo is None:
            occurred_at = occurred_at.replace(tzinfo=timezone.utc)

        return cls(
            event_id=event_id,
            type=str(data["type"]),
            version=version,
            occurred_at=occurred_at,
            producer=str(data["producer"]),
            payload=payload,
            correlation_id=str(data["correlation_id"]),
        )

    @classmethod
    def from_json(cls, raw: str | bytes) -> "EventEnvelope":
        if isinstance(raw, bytes):
            try:
                raw = raw.decode("utf-8")
            except UnicodeDecodeError as exc:
                raise ValueError("event body is not valid UTF-8") from exc
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError("event body is not valid JSON") from exc
        if not isinstance(data, dict):
            raise ValueError("event body must be a JSON object")
        return cls.from_dict(data)
