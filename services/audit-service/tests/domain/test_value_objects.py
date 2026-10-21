import pytest

from domain.audit.exceptions import (
    InvalidActorId,
    InvalidEventPayload,
)
from domain.audit.value_objects import ActorId, EventPayload


def test_actor_id_is_normalized() -> None:
    assert ActorId("  account-1  ").value == "account-1"


def test_actor_id_rejects_blank_value() -> None:
    with pytest.raises(InvalidActorId):
        ActorId("   ")


def test_payload_is_copied() -> None:
    original = {"user_id": "abc"}
    payload = EventPayload(original)
    original["user_id"] = "changed"

    assert payload.value == {"user_id": "abc"}


def test_payload_rejects_non_object() -> None:
    with pytest.raises(InvalidEventPayload):
        EventPayload([])  # type: ignore[arg-type]
