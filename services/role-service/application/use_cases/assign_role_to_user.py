"""Assign a role to an account; idempotent by ``(user_id, role_id)``."""

from application.dto import AssignRoleToUserCommand
from application.exceptions import RoleNotFound
from application.ports.unit_of_work import UnitOfWorkFactory
from domain.role.assignment import UserRoleAssignment
from domain.role.value_objects import AssignmentKey


class AssignRoleToUser:
    def __init__(self, unit_of_work: UnitOfWorkFactory) -> None:
        self._unit_of_work = unit_of_work

    async def execute(self, command: AssignRoleToUserCommand) -> None:
        key = AssignmentKey(
            user_id=command.user_id, role_id=command.role_id
        )

        async with self._unit_of_work() as uow:
            if await uow.roles.get(command.role_id) is None:
                raise RoleNotFound(f"role '{command.role_id}' was not found")
            if await uow.assignments.is_assigned(key):
                return

            assignment = UserRoleAssignment.create(
                user_id=command.user_id, role_id=command.role_id
            )
            inserted = await uow.assignments.add(assignment)
            if not inserted:
                return
            for event in assignment.pull_events():
                await uow.outbox.append(
                    event, correlation_id=command.correlation_id
                )
            await uow.commit()
