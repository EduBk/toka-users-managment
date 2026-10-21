"""Fetch a single user by id, serving it from the read cache when possible."""

from uuid import UUID

from application.exceptions import UserNotFound
from application.ports.unit_of_work import UnitOfWorkFactory
from application.ports.user_cache import UserCache
from domain.user.entity import User


class GetUser:
    def __init__(
        self, unit_of_work: UnitOfWorkFactory, cache: UserCache
    ) -> None:
        self._unit_of_work = unit_of_work
        self._cache = cache

    async def execute(self, user_id: UUID) -> User:
        cached = await self._cache.get_user(user_id)
        if cached is not None:
            return cached

        async with self._unit_of_work() as uow:
            user = await uow.users.get(user_id)
        if user is None:
            raise UserNotFound(f"user '{user_id}' was not found")
        await self._cache.set_user(user)
        return user
