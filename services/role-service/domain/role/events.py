"""Domain events raised when roles are assigned or revoked."""

from dataclasses import dataclass
from typing import Any, ClassVar, Protocol
from uuid import UUID


class DomainEvent(Protocol):
    event_type: ClassVar[str]
    version: ClassVar[int]

    def payload(self) -> dict[str, Any]: ...


@dataclass(frozen=True, slots=True)
class RoleAssigned:
    user_id: UUID
    role_id: UUID

    event_type: ClassVar[str] = "role.assigned"
    version: ClassVar[int] = 1

    def payload(self) -> dict[str, Any]:
        return {"user_id": str(self.user_id), "role_id": str(self.role_id)}


@dataclass(frozen=True, slots=True)
class RoleRevoked:
    user_id: UUID
    role_id: UUID

    event_type: ClassVar[str] = "role.revoked"
    version: ClassVar[int] = 1

    def payload(self) -> dict[str, Any]:
        return {"user_id": str(self.user_id), "role_id": str(self.role_id)}
