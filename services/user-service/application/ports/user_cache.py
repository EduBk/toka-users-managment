"""Outbound port for the read cache of the user context."""

from typing import Protocol
from uuid import UUID

from application.dto import UserPage
from domain.user.entity import User


class UserCache(Protocol):
    """Caches read models; a miss returns ``None`` and never raises."""

    async def get_user(self, user_id: UUID) -> User | None: ...

    async def set_user(self, user: User) -> None: ...

    async def get_page(self, *, page: int, page_size: int) -> UserPage | None: ...

    async def set_page(self, page: UserPage) -> None: ...

    async def invalidate(self, user_id: UUID) -> None:
        """Drop the user detail and make every cached listing stale."""
