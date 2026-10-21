"""User-role assignment aggregate."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import UUID

from domain.role.events import DomainEvent, RoleAssigned, RoleRevoked


@dataclass(slots=True)
class UserRoleAssignment:
    """Assignment of a role to an account, keyed by ``(user_id, role_id)``."""

    user_id: UUID
    role_id: UUID
    assigned_at: datetime
    _events: list[DomainEvent] = field(default_factory=list, repr=False)

    @classmethod
    def create(cls, *, user_id: UUID, role_id: UUID) -> "UserRoleAssignment":
        assignment = cls(
            user_id=user_id,
            role_id=role_id,
            assigned_at=datetime.now(timezone.utc),
        )
        assignment._events.append(
            RoleAssigned(user_id=user_id, role_id=role_id)
        )
        return assignment

    def revoke(self) -> None:
        self._events.append(RoleRevoked(user_id=self.user_id, role_id=self.role_id))

    def pull_events(self) -> list[DomainEvent]:
        events = list(self._events)
        self._events.clear()
        return events
