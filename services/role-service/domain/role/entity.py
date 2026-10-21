"""Role aggregate root and its internal permission entity."""

from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID, uuid4

from domain.role.value_objects import (
    PermissionName,
    RoleDescription,
    RoleName,
)


@dataclass(frozen=True, slots=True)
class Permission:
    """Permission owned by a role and referenced by name."""

    name: PermissionName


@dataclass(slots=True)
class Role:
    """Role with its permissions; the pair is one consistency boundary."""

    id: UUID
    name: RoleName
    description: RoleDescription
    permissions: frozenset[Permission]
    created_at: datetime
    updated_at: datetime

    @classmethod
    def create(
        cls,
        *,
        name: RoleName,
        description: RoleDescription | None = None,
        permissions: frozenset[Permission] | None = None,
    ) -> "Role":
        now = datetime.now(timezone.utc)
        return cls(
            id=uuid4(),
            name=name,
            description=description or RoleDescription(),
            permissions=permissions or frozenset(),
            created_at=now,
            updated_at=now,
        )

    def update_permissions(self, permissions: frozenset[Permission]) -> None:
        if permissions == self.permissions:
            return
        self.permissions = permissions
        self.updated_at = datetime.now(timezone.utc)

    def permission_names(self) -> tuple[str, ...]:
        return tuple(
            sorted(permission.name.value for permission in self.permissions)
        )
