"""Value objects of the audit context."""

import re
from dataclasses import dataclass
from typing import Any

from domain.audit.exceptions import (
    InvalidActorId,
    InvalidEventPayload,
    InvalidEventType,
)

_EVENT_TYPE_PATTERN = re.compile(r"^[a-z][a-z0-9_.-]*$")
_MAX_EVENT_TYPE_LENGTH = 120
_MAX_ACTOR_ID_LENGTH = 254


@dataclass(frozen=True, slots=True)
class EventType:
    """Routing key of the audited event, for example ``user.created``."""

    value: str

    def __post_init__(self) -> None:
        normalized = self.value.strip()
        if (
            not normalized
            or len(normalized) > _MAX_EVENT_TYPE_LENGTH
            or not _EVENT_TYPE_PATTERN.fullmatch(normalized)
        ):
            raise InvalidEventType(f"'{self.value}' is not a valid event type")
        object.__setattr__(self, "value", normalized)

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True, slots=True)
class ActorId:
    """Identifier of the account or user that originated the event."""

    value: str

    def __post_init__(self) -> None:
        normalized = self.value.strip()
        if not normalized or len(normalized) > _MAX_ACTOR_ID_LENGTH:
            raise InvalidActorId("actor_id must be between 1 and 254 characters")
        object.__setattr__(self, "value", normalized)

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True, slots=True)
class EventPayload:
    """Original event payload, kept opaque and unmodified."""

    value: dict[str, Any]

    def __post_init__(self) -> None:
        if not isinstance(self.value, dict):
            raise InvalidEventPayload("event payload must be an object")
        object.__setattr__(self, "value", dict(self.value))
