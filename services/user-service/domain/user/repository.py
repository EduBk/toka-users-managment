"""Outbound port for user persistence."""

from typing import Protocol
from uuid import UUID

from domain.user.entity import User
from domain.user.value_objects import Email


class UserRepository(Protocol):
    async def get(self, user_id: UUID) -> User | None: ...

    async def list(
        self, *, page: int, page_size: int
    ) -> tuple[list[User], int]: ...

    async def exists_by_email(self, email: Email) -> bool: ...

    async def add(self, user: User) -> None: ...

    async def save(self, user: User) -> None: ...
