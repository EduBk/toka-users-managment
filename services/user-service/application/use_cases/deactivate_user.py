"""Apply the logical delete of a user and record ``user.deactivated``."""

from application.dto import DeactivateUserCommand
from application.exceptions import UserNotFound
from application.ports.unit_of_work import UnitOfWorkFactory
from application.ports.user_cache import UserCache
from domain.user.entity import User


class DeactivateUser:
    def __init__(
        self, unit_of_work: UnitOfWorkFactory, cache: UserCache
    ) -> None:
        self._unit_of_work = unit_of_work
        self._cache = cache

    async def execute(self, command: DeactivateUserCommand) -> User:
        async with self._unit_of_work() as uow:
            user = await uow.users.get(command.user_id)
            if user is None:
                raise UserNotFound(
                    f"user '{command.user_id}' was not found"
                )
            if not user.deactivate():
                await self._cache.invalidate(user.id)
                return user

            await uow.users.save(user)
            for event in user.pull_events():
                await uow.outbox.append(
                    event, correlation_id=command.correlation_id
                )
            await uow.commit()
        await self._cache.invalidate(user.id)
        return user
