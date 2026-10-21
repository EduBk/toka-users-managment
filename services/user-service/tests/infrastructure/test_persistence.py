from datetime import datetime, timezone
from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError

from domain.user.entity import User
from domain.user.events import UserCreated
from domain.user.exceptions import EmailAlreadyExists
from domain.user.value_objects import Email, UserName
from infrastructure.persistence.models import OutboxEventModel, UserModel
from infrastructure.persistence.outbox_store import (
    SqlAlchemyOutbox,
    SqlAlchemyOutboxStore,
)
from infrastructure.persistence.unit_of_work import SqlAlchemyUnitOfWork
from infrastructure.persistence.user_repository import SqlAlchemyUserRepository
from tests.infrastructure.fakes import FakeSession


def _user() -> User:
    return User.create(email=Email("ana@example.com"), name=UserName("Ana"))


def _user_model(user: User) -> UserModel:
    return UserModel(
        id=user.id,
        email=user.email.value,
        name=user.name.value,
        status=user.status.value,
        profile={"team": "sales"},
        created_at=user.created_at,
        updated_at=user.updated_at,
    )


async def test_repository_maps_rows_to_the_aggregate() -> None:
    user = _user()
    session = FakeSession(rows=[_user_model(user)], scalar_value=1)
    repository = SqlAlchemyUserRepository(session)  # type: ignore[arg-type]

    found = await repository.get(user.id)
    items, total = await repository.list(page=1, page_size=20)

    assert found is not None
    assert found.email == user.email
    assert found.profile.value == {"team": "sales"}
    assert [item.id for item in items] == [user.id]
    assert total == 1
    assert await repository.get(uuid4()) is None


async def test_repository_checks_email_existence() -> None:
    repository = SqlAlchemyUserRepository(
        FakeSession(scalar_value=uuid4())  # type: ignore[arg-type]
    )

    assert await repository.exists_by_email(Email("ana@example.com")) is True


async def test_repository_add_and_save_flush_the_session() -> None:
    session = FakeSession()
    repository = SqlAlchemyUserRepository(session)  # type: ignore[arg-type]
    user = _user()

    await repository.add(user)
    await repository.save(user)

    assert session.added[0].email == "ana@example.com"
    assert session.merged[0].id == user.id
    assert session.flushes == 2


async def test_repository_translates_integrity_errors() -> None:
    session = FakeSession(
        flush_error=IntegrityError("insert", {}, Exception("duplicate"))
    )
    repository = SqlAlchemyUserRepository(session)  # type: ignore[arg-type]

    with pytest.raises(EmailAlreadyExists):
        await repository.add(_user())


async def test_outbox_store_appends_a_versioned_envelope() -> None:
    session = FakeSession()
    store = SqlAlchemyOutboxStore(session, producer="user-service")  # type: ignore[arg-type]
    user_id = uuid4()

    await store.append(
        UserCreated(
            user_id=user_id, email="ana@example.com", name="Ana", status="active"
        ),
        correlation_id="req-1234",
    )

    record = session.added[0]
    assert isinstance(record, OutboxEventModel)
    assert record.type == "user.created"
    assert record.producer == "user-service"
    assert record.payload["user_id"] == str(user_id)
    assert record.correlation_id == "req-1234"
    assert session.flushes == 1


async def test_outbox_reader_returns_pending_events_and_records_results() -> None:
    event_id = uuid4()
    row = OutboxEventModel(
        event_id=event_id,
        type="user.created",
        version=1,
        occurred_at=datetime.now(timezone.utc),
        producer="user-service",
        payload={"user_id": "u-1"},
        correlation_id="req-1234",
        attempts=2,
    )
    session = FakeSession(rows=[row])
    outbox = SqlAlchemyOutbox(lambda: session)  # type: ignore[arg-type]

    pending = await outbox.pending_batch(10)
    await outbox.mark_published(event_id)
    await outbox.mark_failed(
        event_id, error="boom", retry_at=datetime.now(timezone.utc)
    )

    assert pending[0].event_id == event_id
    assert pending[0].attempts == 2
    assert pending[0].envelope.type == "user.created"
    assert len(session.executed) == 2
    assert session.commits == 2


async def test_unit_of_work_owns_the_session_lifecycle() -> None:
    session = FakeSession()
    uow = SqlAlchemyUnitOfWork(lambda: session, producer="user-service")  # type: ignore[arg-type]

    async with uow:
        await uow.commit()
        await uow.rollback()

    assert session.commits == 1
    assert session.rollbacks == 1
    assert session.closed is True
    with pytest.raises(RuntimeError):
        await uow.commit()
