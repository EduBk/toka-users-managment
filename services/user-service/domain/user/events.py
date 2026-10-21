"""Domain events raised by the user management context."""

from dataclasses import dataclass
from typing import Any, ClassVar, Protocol
from uuid import UUID


class DomainEvent(Protocol):
    event_type: ClassVar[str]
    version: ClassVar[int]

    def payload(self) -> dict[str, Any]: ...


@dataclass(frozen=True, slots=True)
class UserCreated:
    user_id: UUID
    email: str
    name: str
    status: str

    event_type: ClassVar[str] = "user.created"
    version: ClassVar[int] = 1

    def payload(self) -> dict[str, Any]:
        return {
            "user_id": str(self.user_id),
            "email": self.email,
            "name": self.name,
            "status": self.status,
        }


@dataclass(frozen=True, slots=True)
class UserUpdated:
    user_id: UUID
    email: str
    name: str
    status: str

    event_type: ClassVar[str] = "user.updated"
    version: ClassVar[int] = 1

    def payload(self) -> dict[str, Any]:
        return {
            "user_id": str(self.user_id),
            "email": self.email,
            "name": self.name,
            "status": self.status,
        }


@dataclass(frozen=True, slots=True)
class UserDeactivated:
    user_id: UUID
    email: str

    event_type: ClassVar[str] = "user.deactivated"
    version: ClassVar[int] = 1

    def payload(self) -> dict[str, Any]:
        return {"user_id": str(self.user_id), "email": self.email}
