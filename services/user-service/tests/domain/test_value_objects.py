import pytest

from domain.user.exceptions import (
    InvalidEmail,
    InvalidProfile,
    InvalidUserName,
    InvalidUserStatus,
)
from domain.user.value_objects import Email, Profile, UserName, UserStatus


def test_email_is_normalized() -> None:
    assert Email("  Ana@Example.COM ").value == "ana@example.com"


@pytest.mark.parametrize("value", ["not-an-email", "ana@example", "@example.com"])
def test_email_rejects_invalid_values(value: str) -> None:
    with pytest.raises(InvalidEmail):
        Email(value)


def test_user_name_is_trimmed() -> None:
    assert UserName("  Ana Perez  ").value == "Ana Perez"


@pytest.mark.parametrize("value", ["", "   ", "x" * 121])
def test_user_name_rejects_invalid_values(value: str) -> None:
    with pytest.raises(InvalidUserName):
        UserName(value)


def test_user_status_parses_supported_values() -> None:
    assert UserStatus.parse("active") is UserStatus.ACTIVE
    assert UserStatus.parse("inactive") is UserStatus.INACTIVE


def test_user_status_rejects_unknown_values() -> None:
    with pytest.raises(InvalidUserStatus):
        UserStatus.parse("deleted")


def test_profile_copies_the_given_object() -> None:
    source = {"department": "sales"}
    profile = Profile(source)

    source["department"] = "support"

    assert profile.value == {"department": "sales"}


def test_profile_rejects_non_objects() -> None:
    with pytest.raises(InvalidProfile):
        Profile([])  # type: ignore[arg-type]
