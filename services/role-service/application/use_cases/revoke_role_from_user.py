"""Revoke a role from an account; idempotent by ``(user_id, role_id)``."""

from application.dto import RevokeRoleFromUserCommand
from application.ports.unit_of_work import UnitOfWorkFactory
from domain.role.value_objects import AssignmentKey


class RevokeRoleFromUser:
    def __init__(self, unit_of_work: UnitOfWorkFactory) -> None:
        self._unit_of_work = unit_of_work

    async def execute(self, command: RevokeRoleFromUserCommand) -> None:
        key = AssignmentKey(
            user_id=command.user_id, role_id=command.role_id
        )

        async with self._unit_of_work() as uow:
            assignment = await uow.assignments.get(key)
            if assignment is None:
                return
            removed = await uow.assignments.remove(key)
            if not removed:
                return

            assignment.revoke()
            for event in assignment.pull_events():
                await uow.outbox.append(
                    event, correlation_id=command.correlation_id
                )
            await uow.commit()
