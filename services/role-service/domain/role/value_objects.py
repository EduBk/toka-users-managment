"""Value objects of the roles and permissions context."""

import re
from dataclasses import dataclass
from uuid import UUID

from domain.role.exceptions import (
    InvalidPermissionName,
    InvalidRoleDescription,
    InvalidRoleName,
)

_ROLE_NAME_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_-]*$")
_PERMISSION_NAME_PATTERN = re.compile(
    r"^[a-z][a-z0-9_-]*(?::[a-z0-9][a-z0-9_-]*)*$"
)
_MAX_ROLE_NAME_LENGTH = 60
_MAX_DESCRIPTION_LENGTH = 255
_MAX_PERMISSION_LENGTH = 100


@dataclass(frozen=True, slots=True)
class RoleName:
    """Normalized role name, unique in ``roles_db``."""

    value: str

    def __post_init__(self) -> None:
        normalized = self.value.strip().lower()
        if (
            not normalized
            or len(normalized) > _MAX_ROLE_NAME_LENGTH
            or not _ROLE_NAME_PATTERN.fullmatch(normalized)
        ):
            raise InvalidRoleName(
                "role name must be 1-60 lowercase alphanumeric, '-' or '_' characters"
            )
        object.__setattr__(self, "value", normalized)

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True, slots=True)
class RoleDescription:
    """Free-text description of a role."""

    value: str = ""

    def __post_init__(self) -> None:
        normalized = self.value.strip()
        if len(normalized) > _MAX_DESCRIPTION_LENGTH:
            raise InvalidRoleDescription(
                "role description must be at most 255 characters"
            )
        object.__setattr__(self, "value", normalized)

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True, slots=True)
class PermissionName:
    """Permission referenced by name (e.g. ``users:write``, ``ai:use``)."""

    value: str

    def __post_init__(self) -> None:
        normalized = self.value.strip().lower()
        if (
            not normalized
            or len(normalized) > _MAX_PERMISSION_LENGTH
            or not _PERMISSION_NAME_PATTERN.fullmatch(normalized)
        ):
            raise InvalidPermissionName(
                "permission must be lowercase segments separated by ':'"
            )
        object.__setattr__(self, "value", normalized)

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True, slots=True)
class AssignmentKey:
    """Identity of a user-role assignment: ``(user_id, role_id)``.

    ``user_id`` is the ``sub`` claim of the access token (the account id).
    """

    user_id: UUID
    role_id: UUID
