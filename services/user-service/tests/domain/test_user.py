from datetime import timezone

from domain.user.entity import User
from domain.user.events import UserCreated, UserDeactivated, UserUpdated
from domain.user.value_objects import Email, Profile, UserName, UserStatus


def _user(name: str = "Ana Perez") -> User:
    return User.create(
        email=Email("ana@example.com"),
        name=UserName(name),
        profile=Profile({"department": "sales"}),
    )


def test_create_sets_defaults_and_emits_user_created() -> None:
    user = _user()

    assert user.status is UserStatus.ACTIVE
    assert user.created_at.tzinfo == timezone.utc
    assert user.updated_at == user.created_at
    events = user.pull_events()
    assert len(events) == 1
    event = events[0]
    assert isinstance(event, UserCreated)
    assert event.payload() == {
        "user_id": str(user.id),
        "email": "ana@example.com",
        "name": "Ana Perez",
        "status": "active",
    }


def test_update_changes_fields_and_emits_user_updated() -> None:
    user = _user()
    user.pull_events()

    user.update(
        email=Email("ana.perez@example.com"),
        name=UserName("Ana P."),
        profile=Profile({"department": "support"}),
    )

    assert user.email.value == "ana.perez@example.com"
    assert user.name.value == "Ana P."
    assert user.profile.value == {"department": "support"}
    events = user.pull_events()
    assert len(events) == 1
    event = events[0]
    assert isinstance(event, UserUpdated)
    assert event.payload()["name"] == "Ana P."
    assert event.payload()["status"] == "active"


def test_update_without_changes_emits_no_event() -> None:
    user = _user()
    user.pull_events()

    user.update(name=UserName("Ana Perez"))

    assert user.pull_events() == []


def test_deactivate_is_idempotent() -> None:
    user = _user()
    user.pull_events()

    assert user.deactivate() is True
    assert user.status is UserStatus.INACTIVE
    assert user.deactivate() is False

    events = user.pull_events()
    assert len(events) == 1
    event = events[0]
    assert isinstance(event, UserDeactivated)
    assert event.payload() == {
        "user_id": str(user.id),
        "email": "ana@example.com",
    }
