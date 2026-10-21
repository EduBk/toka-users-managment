"""Create a role in the catalog."""

from application.dto import CreateRoleCommand
from application.exceptions import RoleAlreadyExists
from application.ports.unit_of_work import UnitOfWorkFactory
from domain.role.entity import Permission, Role
from domain.role.value_objects import (
    PermissionName,
    RoleDescription,
    RoleName,
)


class CreateRole:
    def __init__(self, unit_of_work: UnitOfWorkFactory) -> None:
        self._unit_of_work = unit_of_work

    async def execute(self, command: CreateRoleCommand) -> Role:
        name = RoleName(command.name)
        description = RoleDescription(command.description)
        permissions = frozenset(
            Permission(PermissionName(value)) for value in command.permissions
        )

        async with self._unit_of_work() as uow:
            if await uow.roles.exists_by_name(name):
                raise RoleAlreadyExists(f"role '{name}' already exists")
            role = Role.create(
                name=name,
                description=description,
                permissions=permissions,
            )
            await uow.roles.add(role)
            await uow.commit()
        return role
