import pytest

from application.dto import UpdateUserCommand
from application.exceptions import UserNotFound
from application.use_cases.update_user import UpdateUser
from domain.user.entity import User
from domain.user.events import UserUpdated
from domain.user.exceptions import EmailAlreadyExists
from domain.user.value_objects import Email, UserName
from tests.application.fakes import FakeUnitOfWork, FakeUserCache


def _user(email: str = "ana@example.com", name: str = "Ana Perez") -> User:
    return User.create(email=Email(email), name=UserName(name))


def _command(
    user: User,
    *,
    email: str | None = None,
    name: str | None = None,
    profile: dict[str, object] | None = None,
) -> UpdateUserCommand:
    return UpdateUserCommand(
        user_id=user.id,
        email=email,
        name=name,
        profile=profile,
        correlation_id="req-5678",
    )


async def test_update_user_changes_fields_and_records_the_event() -> None:
    user = _user()
    user.pull_events()
    uow = FakeUnitOfWork()
    uow.users.users.append(user)
    cache = FakeUserCache()

    result = await UpdateUser(lambda: uow, cache).execute(
        _command(
            user,
            email="ana.perez@example.com",
            name="Ana P.",
            profile={"department": "support"},
        )
    )

    assert result.email.value == "ana.perez@example.com"
    assert result.name.value == "Ana P."
    assert result.profile.value == {"department": "support"}
    assert uow.commits == 1
    assert cache.invalidated == [user.id]
    assert uow.users.saved == [user]
    assert len(uow.outbox.events) == 1
    event, correlation_id = uow.outbox.events[0]
    assert isinstance(event, UserUpdated)
    assert correlation_id == "req-5678"


async def test_update_user_rejects_an_email_used_by_another_user() -> None:
    user = _user()
    uow = FakeUnitOfWork()
    uow.users.users.extend([user, _user("other@example.com", "Other")])

    with pytest.raises(EmailAlreadyExists):
        await UpdateUser(lambda: uow, FakeUserCache()).execute(
            _command(user, email="other@example.com")
        )

    assert uow.commits == 0
    assert uow.outbox.events == []


async def test_update_user_allows_keeping_the_same_email() -> None:
    user = _user()
    user.pull_events()
    uow = FakeUnitOfWork()
    uow.users.users.append(user)

    await UpdateUser(lambda: uow, FakeUserCache()).execute(
        _command(user, email="Ana@Example.com", name="Ana P.")
    )

    assert user.email.value == "ana@example.com"
    assert uow.commits == 1
    assert len(uow.outbox.events) == 1


async def test_update_user_without_changes_emits_no_event() -> None:
    user = _user()
    user.pull_events()
    uow = FakeUnitOfWork()
    uow.users.users.append(user)

    await UpdateUser(lambda: uow, FakeUserCache()).execute(
        _command(user, name="Ana Perez")
    )

    assert uow.outbox.events == []


async def test_update_user_raises_when_missing() -> None:
    user = _user()
    user.pull_events()
    uow = FakeUnitOfWork()

    with pytest.raises(UserNotFound):
        await UpdateUser(lambda: uow, FakeUserCache()).execute(_command(user, name="Ana P."))
