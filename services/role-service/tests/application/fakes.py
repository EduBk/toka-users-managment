"""In-memory doubles for the application ports."""

from types import TracebackType
from uuid import UUID

from domain.role.assignment import UserRoleAssignment
from domain.role.entity import Role
from domain.role.events import DomainEvent
from domain.role.value_objects import AssignmentKey, RoleName


class InMemoryRoleRepository:
    def __init__(self) -> None:
        self.roles: list[Role] = []

    async def get(self, role_id: UUID) -> Role | None:
        return next((role for role in self.roles if role.id == role_id), None)

    async def get_by_name(self, name: RoleName) -> Role | None:
        return next((role for role in self.roles if role.name == name), None)

    async def list(self) -> list[Role]:
        return sorted(self.roles, key=lambda role: role.name.value)

    async def exists_by_name(self, name: RoleName) -> bool:
        return await self.get_by_name(name) is not None

    async def add(self, role: Role) -> None:
        self.roles.append(role)

    async def save(self, role: Role) -> None:
        for index, existing in enumerate(self.roles):
            if existing.id == role.id:
                self.roles[index] = role
                return
        self.roles.append(role)


class InMemoryAssignmentRepository:
    def __init__(self, roles: InMemoryRoleRepository) -> None:
        self._roles = roles
        self.assignments: dict[tuple[UUID, UUID], UserRoleAssignment] = {}

    async def get(
        self, key: AssignmentKey
    ) -> UserRoleAssignment | None:
        return self.assignments.get((key.user_id, key.role_id))

    async def is_assigned(self, key: AssignmentKey) -> bool:
        return (key.user_id, key.role_id) in self.assignments

    async def add(self, assignment: UserRoleAssignment) -> bool:
        key = (assignment.user_id, assignment.role_id)
        if key in self.assignments:
            return False
        self.assignments[key] = assignment
        return True

    async def remove(self, key: AssignmentKey) -> bool:
        return (
            self.assignments.pop((key.user_id, key.role_id), None) is not None
        )

    async def roles_for_user(self, user_id: UUID) -> list[Role]:
        role_ids = {
            role_id
            for (assigned_user, role_id) in self.assignments
            if assigned_user == user_id
        }
        return sorted(
            (role for role in self._roles.roles if role.id in role_ids),
            key=lambda role: role.name.value,
        )

    async def permissions_for_user(self, user_id: UUID) -> tuple[str, ...]:
        permissions = {
            permission
            for role in await self.roles_for_user(user_id)
            for permission in role.permission_names()
        }
        return tuple(sorted(permissions))


class FakeEventOutbox:
    def __init__(self) -> None:
        self.events: list[tuple[DomainEvent, str]] = []

    async def append(
        self, event: DomainEvent, *, correlation_id: str
    ) -> None:
        self.events.append((event, correlation_id))


class FakeUnitOfWork:
    def __init__(self, roles: InMemoryRoleRepository | None = None) -> None:
        self.roles = roles or InMemoryRoleRepository()
        self.assignments = InMemoryAssignmentRepository(self.roles)
        self.outbox = FakeEventOutbox()
        self.commits = 0
        self.rollbacks = 0

    async def __aenter__(self) -> "FakeUnitOfWork":
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        return None

    async def commit(self) -> None:
        self.commits += 1

    async def rollback(self) -> None:
        self.rollbacks += 1
