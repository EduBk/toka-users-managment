import pytest

from application.dto import DeactivateUserCommand
from application.exceptions import UserNotFound
from application.use_cases.deactivate_user import DeactivateUser
from domain.user.entity import User
from domain.user.events import UserDeactivated
from domain.user.value_objects import Email, UserName, UserStatus
from tests.application.fakes import FakeUnitOfWork, FakeUserCache


def _user() -> User:
    return User.create(
        email=Email("ana@example.com"), name=UserName("Ana Perez")
    )


async def test_deactivate_user_applies_the_logical_delete() -> None:
    user = _user()
    user.pull_events()
    uow = FakeUnitOfWork()
    uow.users.users.append(user)
    cache = FakeUserCache()

    result = await DeactivateUser(lambda: uow, cache).execute(
        DeactivateUserCommand(user_id=user.id, correlation_id="req-9999")
    )

    assert result.status is UserStatus.INACTIVE
    assert uow.commits == 1
    assert cache.invalidated == [user.id]
    assert len(uow.outbox.events) == 1
    event, correlation_id = uow.outbox.events[0]
    assert isinstance(event, UserDeactivated)
    assert correlation_id == "req-9999"


async def test_deactivate_user_is_idempotent() -> None:
    user = _user()
    user.deactivate()
    user.pull_events()
    uow = FakeUnitOfWork()
    uow.users.users.append(user)
    cache = FakeUserCache()

    result = await DeactivateUser(lambda: uow, cache).execute(
        DeactivateUserCommand(user_id=user.id, correlation_id="req-9999")
    )

    assert result.status is UserStatus.INACTIVE
    assert uow.commits == 0
    assert cache.invalidated == [user.id]
    assert uow.outbox.events == []


async def test_deactivate_user_raises_when_missing() -> None:
    uow = FakeUnitOfWork()

    with pytest.raises(UserNotFound):
        await DeactivateUser(lambda: uow, FakeUserCache()).execute(
            DeactivateUserCommand(user_id=_user().id, correlation_id="req-9999")
        )
