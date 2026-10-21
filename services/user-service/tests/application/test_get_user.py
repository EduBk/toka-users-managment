import pytest

from application.exceptions import UserNotFound
from application.use_cases.get_user import GetUser
from domain.user.entity import User
from domain.user.value_objects import Email, UserName
from tests.application.fakes import FakeUnitOfWork, FakeUserCache


async def test_get_user_returns_the_aggregate() -> None:
    user = User.create(
        email=Email("ana@example.com"), name=UserName("Ana Perez")
    )
    uow = FakeUnitOfWork()
    uow.users.users.append(user)

    result = await GetUser(lambda: uow, FakeUserCache()).execute(user.id)

    assert result is user


async def test_get_user_raises_when_missing() -> None:
    uow = FakeUnitOfWork()

    with pytest.raises(UserNotFound):
        await GetUser(lambda: uow, FakeUserCache()).execute(
            User.create(
                email=Email("ana@example.com"), name=UserName("Ana Perez")
            ).id
        )


async def test_get_user_serves_the_second_read_from_cache() -> None:
    user = User.create(
        email=Email("ana@example.com"), name=UserName("Ana Perez")
    )
    uow = FakeUnitOfWork()
    uow.users.users.append(user)
    cache = FakeUserCache()
    use_case = GetUser(lambda: uow, cache)

    first = await use_case.execute(user.id)
    uow.users.users.clear()
    second = await use_case.execute(user.id)

    assert first is user
    assert second.id == user.id
    assert second.email == user.email
    assert cache.writes == 1


async def test_get_user_does_not_cache_a_missing_user() -> None:
    user = User.create(
        email=Email("ana@example.com"), name=UserName("Ana Perez")
    )
    cache = FakeUserCache()

    with pytest.raises(UserNotFound):
        await GetUser(lambda: FakeUnitOfWork(), cache).execute(user.id)

    assert cache.writes == 0
