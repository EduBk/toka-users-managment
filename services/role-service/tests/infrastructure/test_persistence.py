from datetime import datetime, timezone
from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError

from application.exceptions import RoleAlreadyExists
from domain.role.assignment import UserRoleAssignment
from domain.role.entity import Permission, Role
from domain.role.events import RoleAssigned
from domain.role.value_objects import AssignmentKey, PermissionName, RoleName
from infrastructure.persistence.models import (
    OutboxEventModel,
    RoleModel,
    RolePermissionModel,
    UserRoleModel,
)
from infrastructure.persistence.outbox_store import (
    SqlAlchemyOutbox,
    SqlAlchemyOutboxStore,
)
from infrastructure.persistence.role_repository import (
    SqlAlchemyAssignmentRepository,
    SqlAlchemyRoleRepository,
)
from infrastructure.persistence.unit_of_work import SqlAlchemyUnitOfWork
from tests.infrastructure.fakes import FakeSession


def _role() -> Role:
    return Role.create(
        name=RoleName("auditor"),
        permissions=frozenset({Permission(PermissionName("audit:read"))}),
    )


def _role_model(role: Role) -> RoleModel:
    return RoleModel(
        id=role.id,
        name=role.name.value,
        description=role.description.value,
        created_at=role.created_at,
        updated_at=role.updated_at,
    )


async def test_role_repository_maps_roles_with_their_permissions() -> None:
    role = _role()
    model = _role_model(role)
    session = FakeSession(
        models=[model],
        scalar=[model, role.id, None],
        scalars=[[model]],
        execute_rows=[(role.id, "audit:read")],
    )
    repository = SqlAlchemyRoleRepository(session)  # type: ignore[arg-type]

    by_id = await repository.get(role.id)
    by_name = await repository.get_by_name(RoleName("auditor"))
    listed = await repository.list()

    assert by_id is not None and by_id.permission_names() == ("audit:read",)
    assert by_name is not None and by_name.id == role.id
    assert [item.id for item in listed] == [role.id]
    assert await repository.exists_by_name(RoleName("auditor")) is True
    assert await repository.exists_by_name(RoleName("missing")) is False
    assert await repository.get(uuid4()) is None


async def test_role_repository_writes_role_and_permission_rows() -> None:
    session = FakeSession()
    repository = SqlAlchemyRoleRepository(session)  # type: ignore[arg-type]
    role = _role()

    await repository.add(role)
    await repository.save(role)

    assert isinstance(session.added[0], RoleModel)
    assert isinstance(session.added[1], RolePermissionModel)
    assert session.merged[0].id == role.id
    assert len(session.executed) == 1
    assert session.flushes == 2


async def test_role_repository_translates_integrity_errors() -> None:
    session = FakeSession(
        flush_error=IntegrityError("insert", {}, Exception("duplicate"))
    )

    with pytest.raises(RoleAlreadyExists):
        await SqlAlchemyRoleRepository(session).add(_role())  # type: ignore[arg-type]


async def test_assignment_repository_reads_and_writes_assignments() -> None:
    role = _role()
    user_id = uuid4()
    key = AssignmentKey(user_id=user_id, role_id=role.id)
    assigned_at = datetime.now(timezone.utc)
    session = FakeSession(
        scalar=[
            UserRoleModel(
                user_id=user_id, role_id=role.id, assigned_at=assigned_at
            ),
            user_id,
            user_id,
        ],
        scalars=[[role.id], [_role_model(role)], ["audit:read"]],
        execute_rows=[(role.id, "audit:read")],
        rowcount=1,
    )
    repository = SqlAlchemyAssignmentRepository(session)  # type: ignore[arg-type]

    found = await repository.get(key)
    assigned = await repository.is_assigned(key)
    added = await repository.add(
        UserRoleAssignment.create(user_id=user_id, role_id=role.id)
    )
    roles = await repository.roles_for_user(user_id)
    permissions = await repository.permissions_for_user(user_id)
    removed = await repository.remove(key)

    assert found is not None and found.assigned_at == assigned_at
    assert assigned is True
    assert added is True
    assert [item.name.value for item in roles] == ["auditor"]
    assert permissions == ("audit:read",)
    assert removed is True


async def test_assignment_repository_handles_missing_rows() -> None:
    repository = SqlAlchemyAssignmentRepository(FakeSession())  # type: ignore[arg-type]
    key = AssignmentKey(user_id=uuid4(), role_id=uuid4())

    assert await repository.get(key) is None
    assert await repository.is_assigned(key) is False
    assert await repository.roles_for_user(key.user_id) == []


async def test_outbox_store_and_reader_round_trip() -> None:
    session = FakeSession()
    store = SqlAlchemyOutboxStore(session, producer="role-service")  # type: ignore[arg-type]
    user_id, role_id = uuid4(), uuid4()

    await store.append(
        RoleAssigned(user_id=user_id, role_id=role_id),
        correlation_id="req-1234",
    )
    record: OutboxEventModel = session.added[0]
    record.attempts = 0
    reader_session = FakeSession(scalars=[[record]])
    outbox = SqlAlchemyOutbox(lambda: reader_session)  # type: ignore[arg-type]

    pending = await outbox.pending_batch(10)
    await outbox.mark_published(record.event_id)
    await outbox.mark_failed(
        record.event_id, error="boom", retry_at=datetime.now(timezone.utc)
    )

    assert record.type == "role.assigned"
    assert record.payload == {"user_id": str(user_id), "role_id": str(role_id)}
    assert pending[0].envelope.producer == "role-service"
    assert reader_session.commits == 2


async def test_unit_of_work_owns_the_session_lifecycle() -> None:
    session = FakeSession()
    uow = SqlAlchemyUnitOfWork(lambda: session, producer="role-service")  # type: ignore[arg-type]

    async with uow:
        await uow.commit()
        await uow.rollback()

    assert (session.commits, session.rollbacks, session.closed) == (1, 1, True)
    with pytest.raises(RuntimeError):
        await uow.rollback()
