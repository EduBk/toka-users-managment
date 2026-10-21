"""Commands accepted by the role use cases."""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True, slots=True)
class CreateRoleCommand:
    name: str
    description: str
    permissions: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class UpdateRolePermissionsCommand:
    role_id: UUID
    permissions: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class AssignRoleToUserCommand:
    user_id: UUID
    role_id: UUID
    correlation_id: str


@dataclass(frozen=True, slots=True)
class RevokeRoleFromUserCommand:
    user_id: UUID
    role_id: UUID
    correlation_id: str
