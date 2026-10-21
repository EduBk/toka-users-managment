from datetime import datetime, timezone
from uuid import uuid4

import pytest

from app_common.event_envelope import EventEnvelope


def test_create_builds_the_versioned_envelope() -> None:
    envelope = EventEnvelope.create(
        type="user.created",
        producer="user-service",
        payload={"user_id": "8b1d", "email": "ana@example.com"},
        correlation_id="req-7f3a91",
    )

    assert envelope.version == 1
    assert envelope.type == "user.created"
    assert envelope.producer == "user-service"
    assert envelope.correlation_id == "req-7f3a91"
    assert envelope.occurred_at.tzinfo is not None


def test_json_round_trip_preserves_every_field() -> None:
    occurred_at = datetime(2026, 10, 20, 14, 32, 11, 482000, tzinfo=timezone.utc)
    event_id = uuid4()
    envelope = EventEnvelope.create(
        event_id=event_id,
        type="role.assigned",
        version=2,
        occurred_at=occurred_at,
        producer="role-service",
        payload={"user_id": "u-1", "role_id": "r-1"},
        correlation_id="req-7f3a91",
    )

    decoded = EventEnvelope.from_json(envelope.to_json().encode("utf-8"))

    assert decoded == envelope
    assert decoded.event_id == event_id


def test_from_json_rejects_missing_fields() -> None:
    with pytest.raises(ValueError, match="missing envelope fields"):
        EventEnvelope.from_json('{"type":"user.created"}')


def test_from_json_rejects_an_invalid_body() -> None:
    with pytest.raises(ValueError, match="not valid JSON"):
        EventEnvelope.from_json("not-json")


def test_from_json_assumes_utc_when_the_timestamp_has_no_timezone() -> None:
    envelope = EventEnvelope.from_dict(
        {
            "event_id": str(uuid4()),
            "type": "user.logged_in",
            "version": 1,
            "occurred_at": "2026-10-20T14:32:11",
            "producer": "auth-service",
            "payload": {"email": "ana@example.com"},
            "correlation_id": "req-7f3a91",
        }
    )

    assert envelope.occurred_at == datetime(
        2026, 10, 20, 14, 32, 11, tzinfo=timezone.utc
    )
