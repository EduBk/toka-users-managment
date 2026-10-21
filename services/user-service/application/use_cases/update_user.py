"""Update mutable user data and record ``user.updated``."""

from application.dto import UpdateUserCommand
from application.exceptions import UserNotFound
from application.ports.unit_of_work import UnitOfWorkFactory
from application.ports.user_cache import UserCache
from domain.user.entity import User
from domain.user.exceptions import EmailAlreadyExists
from domain.user.value_objects import Email, Profile, UserName


class UpdateUser:
    def __init__(
        self, unit_of_work: UnitOfWorkFactory, cache: UserCache
    ) -> None:
        self._unit_of_work = unit_of_work
        self._cache = cache

    async def execute(self, command: UpdateUserCommand) -> User:
        email = Email(command.email) if command.email is not None else None
        name = UserName(command.name) if command.name is not None else None
        profile = (
            Profile(command.profile) if command.profile is not None else None
        )

        async with self._unit_of_work() as uow:
            user = await uow.users.get(command.user_id)
            if user is None:
                raise UserNotFound(
                    f"user '{command.user_id}' was not found"
                )
            if (
                email is not None
                and email != user.email
                and await uow.users.exists_by_email(email)
            ):
                raise EmailAlreadyExists(
                    f"email '{email}' is already registered"
                )

            user.update(email=email, name=name, profile=profile)
            await uow.users.save(user)
            for event in user.pull_events():
                await uow.outbox.append(
                    event, correlation_id=command.correlation_id
                )
            await uow.commit()
        await self._cache.invalidate(user.id)
        return user
