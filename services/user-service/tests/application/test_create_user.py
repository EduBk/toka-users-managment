import pytest

from application.dto import CreateUserCommand
from application.use_cases.create_user import CreateUser
from domain.user.entity import User
from domain.user.events import UserCreated
from domain.user.exceptions import (
    EmailAlreadyExists,
    InvalidEmail,
    InvalidUserName,
)
from domain.user.value_objects import Email, UserName
from tests.application.fakes import FakeUnitOfWork, FakeUserCache


def _command(
    *,
    email: str = "Ana@Example.com",
    name: str = "Ana Perez",
    profile: dict[str, object] | None = None,
) -> CreateUserCommand:
    return CreateUserCommand(
        email=email,
        name=name,
        profile=profile or {"department": "sales"},
        correlation_id="req-1234",
    )


async def test_create_user_persists_and_records_the_event() -> None:
    uow = FakeUnitOfWork()
    cache = FakeUserCache()
    use_case = CreateUser(lambda: uow, cache)

    user = await use_case.execute(_command())

    assert uow.users.users == [user]
    assert user.email.value == "ana@example.com"
    assert user.profile.value == {"department": "sales"}
    assert uow.commits == 1
    assert cache.invalidated == [user.id]
    assert len(uow.outbox.events) == 1
    event, correlation_id = uow.outbox.events[0]
    assert isinstance(event, UserCreated)
    assert event.payload()["user_id"] == str(user.id)
    assert correlation_id == "req-1234"


async def test_create_user_rejects_a_duplicated_email() -> None:
    uow = FakeUnitOfWork()
    uow.users.users.append(
        User.create(
            email=Email("ana@example.com"),
            name=UserName("Existing"),
        )
    )
    use_case = CreateUser(lambda: uow, FakeUserCache())

    with pytest.raises(EmailAlreadyExists):
        await use_case.execute(_command())

    assert uow.commits == 0
    assert uow.outbox.events == []


async def test_create_user_rejects_an_invalid_email() -> None:
    uow = FakeUnitOfWork()
    use_case = CreateUser(lambda: uow, FakeUserCache())

    with pytest.raises(InvalidEmail):
        await use_case.execute(_command(email="not-an-email"))

    assert uow.commits == 0


async def test_create_user_rejects_an_invalid_name() -> None:
    uow = FakeUnitOfWork()
    use_case = CreateUser(lambda: uow, FakeUserCache())

    with pytest.raises(InvalidUserName):
        await use_case.execute(_command(name="   "))

    assert uow.commits == 0
