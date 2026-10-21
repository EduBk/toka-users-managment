"""Create a user and record ``user.created`` in the same transaction."""

from application.dto import CreateUserCommand
from application.ports.unit_of_work import UnitOfWorkFactory
from application.ports.user_cache import UserCache
from domain.user.entity import User
from domain.user.exceptions import EmailAlreadyExists
from domain.user.value_objects import Email, Profile, UserName


class CreateUser:
    def __init__(
        self, unit_of_work: UnitOfWorkFactory, cache: UserCache
    ) -> None:
        self._unit_of_work = unit_of_work
        self._cache = cache

    async def execute(self, command: CreateUserCommand) -> User:
        email = Email(command.email)
        name = UserName(command.name)
        profile = Profile(command.profile)

        async with self._unit_of_work() as uow:
            if await uow.users.exists_by_email(email):
                raise EmailAlreadyExists(
                    f"email '{email}' is already registered"
                )

            user = User.create(email=email, name=name, profile=profile)
            await uow.users.add(user)
            for event in user.pull_events():
                await uow.outbox.append(
                    event, correlation_id=command.correlation_id
                )
            await uow.commit()
        await self._cache.invalidate(user.id)
        return user
