from uuid import uuid4

import pytest

from application.dto import (
    AssignRoleToUserCommand,
    CreateRoleCommand,
    RevokeRoleFromUserCommand,
    UpdateRolePermissionsCommand,
)
from application.exceptions import RoleAlreadyExists, RoleNotFound
from application.use_cases.assign_role_to_user import AssignRoleToUser
from application.use_cases.create_role import CreateRole
from application.use_cases.get_user_permissions import GetUserPermissions
from application.use_cases.get_user_roles import GetUserRoles
from application.use_cases.list_roles import ListRoles
from application.use_cases.revoke_role_from_user import RevokeRoleFromUser
from application.use_cases.update_role_permissions import UpdateRolePermissions
from domain.role.entity import Permission, Role
from domain.role.events import RoleAssigned, RoleRevoked
from domain.role.exceptions import InvalidPermissionName
from domain.role.value_objects import PermissionName, RoleName
from tests.application.fakes import FakeUnitOfWork


def _role(name: str, *permissions: str) -> Role:
    return Role.create(
        name=RoleName(name),
        permissions=frozenset(
            Permission(PermissionName(permission))
            for permission in permissions
        ),
    )


def _create_command(
    name: str = "support",
    *permissions: str,
) -> CreateRoleCommand:
    return CreateRoleCommand(
        name=name,
        description="Support agents",
        permissions=permissions,
    )


async def test_create_role_persists_without_events() -> None:
    uow = FakeUnitOfWork()

    role = await CreateRole(lambda: uow).execute(
        _create_command("support", "users:read")
    )

    assert uow.roles.roles == [role]
    assert role.permission_names() == ("users:read",)
    assert uow.commits == 1
    assert uow.outbox.events == []


async def test_create_role_rejects_a_duplicated_name() -> None:
    uow = FakeUnitOfWork()
    uow.roles.roles.append(_role("support"))

    with pytest.raises(RoleAlreadyExists):
        await CreateRole(lambda: uow).execute(_create_command("Support"))

    assert uow.commits == 0


async def test_create_role_rejects_an_invalid_permission() -> None:
    uow = FakeUnitOfWork()

    with pytest.raises(InvalidPermissionName):
        await CreateRole(lambda: uow).execute(
            _create_command("support", "users write")
        )

    assert uow.commits == 0


async def test_list_roles_returns_the_catalog_sorted_by_name() -> None:
    uow = FakeUnitOfWork()
    uow.roles.roles.extend([_role("user"), _role("admin")])

    roles = await ListRoles(lambda: uow).execute()

    assert [role.name.value for role in roles] == ["admin", "user"]


async def test_update_role_permissions_replaces_the_set() -> None:
    uow = FakeUnitOfWork()
    role = _role("auditor", "audit:read")
    uow.roles.roles.append(role)

    updated = await UpdateRolePermissions(lambda: uow).execute(
        UpdateRolePermissionsCommand(
            role_id=role.id,
            permissions=("audit:read", "ai:use"),
        )
    )

    assert updated.permission_names() == ("ai:use", "audit:read")
    assert uow.commits == 1


async def test_update_role_permissions_raises_when_missing() -> None:
    uow = FakeUnitOfWork()

    with pytest.raises(RoleNotFound):
        await UpdateRolePermissions(lambda: uow).execute(
            UpdateRolePermissionsCommand(
                role_id=uuid4(), permissions=("ai:use",)
            )
        )

    assert uow.commits == 0


async def test_assign_role_persists_and_emits_role_assigned() -> None:
    uow = FakeUnitOfWork()
    role = _role("auditor", "audit:read")
    uow.roles.roles.append(role)
    user_id = uuid4()

    await AssignRoleToUser(lambda: uow).execute(
        AssignRoleToUserCommand(
            user_id=user_id,
            role_id=role.id,
            correlation_id="req-1234",
        )
    )

    key = (user_id, role.id)
    assert key in uow.assignments.assignments
    assert uow.commits == 1
    event, correlation_id = uow.outbox.events[0]
    assert isinstance(event, RoleAssigned)
    assert event.payload() == {
        "user_id": str(user_id),
        "role_id": str(role.id),
    }
    assert correlation_id == "req-1234"


async def test_assign_role_is_idempotent() -> None:
    uow = FakeUnitOfWork()
    role = _role("auditor", "audit:read")
    uow.roles.roles.append(role)
    user_id = uuid4()
    use_case = AssignRoleToUser(lambda: uow)
    command = AssignRoleToUserCommand(
        user_id=user_id, role_id=role.id, correlation_id="req-1234"
    )

    await use_case.execute(command)
    await use_case.execute(command)

    assert len(uow.assignments.assignments) == 1
    assert len(uow.outbox.events) == 1
    assert uow.commits == 1


async def test_assign_role_raises_when_the_role_does_not_exist() -> None:
    uow = FakeUnitOfWork()

    with pytest.raises(RoleNotFound):
        await AssignRoleToUser(lambda: uow).execute(
            AssignRoleToUserCommand(
                user_id=uuid4(),
                role_id=uuid4(),
                correlation_id="req-1234",
            )
        )

    assert uow.commits == 0


async def test_revoke_role_removes_the_assignment_and_emits_role_revoked() -> None:
    uow = FakeUnitOfWork()
    role = _role("auditor", "audit:read")
    uow.roles.roles.append(role)
    user_id = uuid4()
    await AssignRoleToUser(lambda: uow).execute(
        AssignRoleToUserCommand(
            user_id=user_id, role_id=role.id, correlation_id="req-1"
        )
    )
    uow.outbox.events.clear()

    await RevokeRoleFromUser(lambda: uow).execute(
        RevokeRoleFromUserCommand(
            user_id=user_id, role_id=role.id, correlation_id="req-2"
        )
    )

    assert (user_id, role.id) not in uow.assignments.assignments
    assert uow.commits == 2
    event, correlation_id = uow.outbox.events[0]
    assert isinstance(event, RoleRevoked)
    assert event.payload() == {
        "user_id": str(user_id),
        "role_id": str(role.id),
    }
    assert correlation_id == "req-2"


async def test_revoke_role_is_idempotent() -> None:
    uow = FakeUnitOfWork()
    role = _role("auditor", "audit:read")
    uow.roles.roles.append(role)

    await RevokeRoleFromUser(lambda: uow).execute(
        RevokeRoleFromUserCommand(
            user_id=uuid4(), role_id=role.id, correlation_id="req-1"
        )
    )

    assert uow.commits == 0
    assert uow.outbox.events == []


async def test_get_user_roles_and_permissions_are_derived_from_assignments() -> None:
    uow = FakeUnitOfWork()
    auditor = _role("auditor", "audit:read")
    user = _role("user", "ai:use")
    uow.roles.roles.extend([auditor, user])
    user_id = uuid4()
    await AssignRoleToUser(lambda: uow).execute(
        AssignRoleToUserCommand(
            user_id=user_id, role_id=auditor.id, correlation_id="req-1"
        )
    )
    await AssignRoleToUser(lambda: uow).execute(
        AssignRoleToUserCommand(
            user_id=user_id, role_id=user.id, correlation_id="req-2"
        )
    )

    roles = await GetUserRoles(lambda: uow).execute(user_id)
    permissions = await GetUserPermissions(lambda: uow).execute(user_id)

    assert [role.name.value for role in roles] == ["auditor", "user"]
    assert permissions == ("ai:use", "audit:read")
