"""Value objects of the user management context."""

import re
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from domain.user.exceptions import (
    InvalidEmail,
    InvalidProfile,
    InvalidUserName,
    InvalidUserStatus,
)

_EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_MAX_EMAIL_LENGTH = 254
_MAX_NAME_LENGTH = 120


@dataclass(frozen=True, slots=True)
class Email:
    """Validated and normalized email address."""

    value: str

    def __post_init__(self) -> None:
        normalized = self.value.strip().lower()
        if len(normalized) > _MAX_EMAIL_LENGTH or not _EMAIL_PATTERN.fullmatch(
            normalized
        ):
            raise InvalidEmail(f"'{self.value}' is not a valid email")
        object.__setattr__(self, "value", normalized)

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True, slots=True)
class UserName:
    """Display name of a user."""

    value: str

    def __post_init__(self) -> None:
        normalized = self.value.strip()
        if not normalized or len(normalized) > _MAX_NAME_LENGTH:
            raise InvalidUserName("name must be between 1 and 120 characters")
        object.__setattr__(self, "value", normalized)

    def __str__(self) -> str:
        return self.value


class UserStatus(StrEnum):
    ACTIVE = "active"
    INACTIVE = "inactive"

    @classmethod
    def parse(cls, value: str) -> "UserStatus":
        try:
            return cls(value)
        except ValueError as exc:
            raise InvalidUserStatus(
                f"'{value}' is not a valid user status"
            ) from exc


@dataclass(frozen=True, slots=True)
class Profile:
    """Optional user attributes kept as a JSON object.

    The service does not impose a schema on them; consumers treat the object as
    opaque metadata.
    """

    value: dict[str, Any]

    def __post_init__(self) -> None:
        if not isinstance(self.value, dict):
            raise InvalidProfile("profile must be an object")
        object.__setattr__(self, "value", dict(self.value))

    @classmethod
    def empty(cls) -> "Profile":
        return cls({})
