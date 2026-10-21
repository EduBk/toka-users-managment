"""Commands, queries and results accepted by the user use cases."""

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from domain.user.entity import User


@dataclass(frozen=True, slots=True)
class CreateUserCommand:
    email: str
    name: str
    profile: dict[str, Any]
    correlation_id: str


@dataclass(frozen=True, slots=True)
class UpdateUserCommand:
    user_id: UUID
    email: str | None
    name: str | None
    profile: dict[str, Any] | None
    correlation_id: str


@dataclass(frozen=True, slots=True)
class DeactivateUserCommand:
    user_id: UUID
    correlation_id: str


@dataclass(frozen=True, slots=True)
class ListUsersQuery:
    page: int
    page_size: int


@dataclass(frozen=True, slots=True)
class UserPage:
    items: list[User]
    total: int
    page: int
    page_size: int
