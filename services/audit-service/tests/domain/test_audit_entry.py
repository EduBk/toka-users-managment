from datetime import datetime, timezone
from uuid import uuid4

import pytest

from domain.audit.entity import AuditEntry
from domain.audit.exceptions import InvalidAuditEntry, InvalidEventType
from domain.audit.value_objects import EventType


def _entry(**overrides: object) -> AuditEntry:
    values: dict[str, object] = {
        "event_id": uuid4(),
        "event_type": "user.created",
        "version": 1,
        "occurred_at": datetime(2026, 10, 20, 12, 0, tzinfo=timezone.utc),
        "producer": "user-service",
        "payload": {"user_id": str(uuid4())},
        "correlation_id": "req-1234",
        "actor_id": None,
    }
    values.update(overrides)
    return AuditEntry.create(**values)  # type: ignore[arg-type]


def test_create_keeps_event_fields() -> None:
    event_id = uuid4()
    actor_id = str(uuid4())

    entry = _entry(
        event_id=event_id,
        actor_id=actor_id,
        payload={"user_id": actor_id},
    )

    assert entry.event_id == event_id
    assert entry.type.value == "user.created"
    assert entry.actor_id is not None
    assert entry.actor_id.value == actor_id
    assert entry.payload.value["user_id"] == actor_id


def test_create_rejects_non_positive_version() -> None:
    with pytest.raises(InvalidAuditEntry):
        _entry(version=0)


def test_create_rejects_naive_timestamp() -> None:
    with pytest.raises(InvalidAuditEntry):
        _entry(occurred_at=datetime(2026, 10, 20, 12, 0))


def test_event_type_is_normalized() -> None:
    assert EventType("  user.logged_in  ").value == "user.logged_in"


def test_event_type_rejects_unsupported_format() -> None:
    with pytest.raises(InvalidEventType):
        EventType("User Created")
