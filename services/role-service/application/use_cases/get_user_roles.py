"""Read the roles assigned to an account."""

from uuid import UUID

from application.ports.unit_of_work import UnitOfWorkFactory
from domain.role.entity import Role


class GetUserRoles:
    def __init__(self, unit_of_work: UnitOfWorkFactory) -> None:
        self._unit_of_work = unit_of_work

    async def execute(self, user_id: UUID) -> list[Role]:
        async with self._unit_of_work() as uow:
            return await uow.assignments.roles_for_user(user_id)
