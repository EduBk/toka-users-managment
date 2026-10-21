"""List every role in the catalog."""

from application.ports.unit_of_work import UnitOfWorkFactory
from domain.role.entity import Role


class ListRoles:
    def __init__(self, unit_of_work: UnitOfWorkFactory) -> None:
        self._unit_of_work = unit_of_work

    async def execute(self) -> list[Role]:
        async with self._unit_of_work() as uow:
            return await uow.roles.list()
