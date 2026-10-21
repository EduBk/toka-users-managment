"""Replace the permission set of an existing role."""

from application.dto import UpdateRolePermissionsCommand
from application.exceptions import RoleNotFound
from application.ports.unit_of_work import UnitOfWorkFactory
from domain.role.entity import Permission, Role
from domain.role.value_objects import PermissionName


class UpdateRolePermissions:
    def __init__(self, unit_of_work: UnitOfWorkFactory) -> None:
        self._unit_of_work = unit_of_work

    async def execute(self, command: UpdateRolePermissionsCommand) -> Role:
        permissions = frozenset(
            Permission(PermissionName(value)) for value in command.permissions
        )

        async with self._unit_of_work() as uow:
            role = await uow.roles.get(command.role_id)
            if role is None:
                raise RoleNotFound(f"role '{command.role_id}' was not found")
            role.update_permissions(permissions)
            await uow.roles.save(role)
            await uow.commit()
        return role
