"""Read the effective permissions of an account."""

from uuid import UUID

from application.ports.unit_of_work import UnitOfWorkFactory


class GetUserPermissions:
    def __init__(self, unit_of_work: UnitOfWorkFactory) -> None:
        self._unit_of_work = unit_of_work

    async def execute(self, user_id: UUID) -> tuple[str, ...]:
        async with self._unit_of_work() as uow:
            return await uow.assignments.permissions_for_user(user_id)
