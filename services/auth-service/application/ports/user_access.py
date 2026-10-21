"""Port and result type for resolving an account's roles and permissions."""

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID


@dataclass(frozen=True, slots=True)
class UserAccess:
    """Roles and effective scopes granted to an account."""

    roles: tuple[str, ...] = ()
    scopes: tuple[str, ...] = ()


class UserAccessProvider(Protocol):
    async def access_for(self, user_id: UUID) -> UserAccess: ...
