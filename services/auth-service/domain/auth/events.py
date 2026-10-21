"""Domain events raised by the identity context."""

from dataclasses import dataclass
from typing import Any, ClassVar, Protocol
from uuid import UUID


class DomainEvent(Protocol):
    event_type: ClassVar[str]
    version: ClassVar[int]

    def payload(self) -> dict[str, Any]: ...


@dataclass(frozen=True, slots=True)
class UserLoggedIn:
    user_id: UUID
    email: str

    event_type: ClassVar[str] = "user.logged_in"
    version: ClassVar[int] = 1

    def payload(self) -> dict[str, Any]:
        return {"user_id": str(self.user_id), "email": self.email}


@dataclass(frozen=True, slots=True)
class UserLoginFailed:
    email: str
    reason: str

    event_type: ClassVar[str] = "user.login_failed"
    version: ClassVar[int] = 1

    def payload(self) -> dict[str, Any]:
        return {"email": self.email, "reason": self.reason}
