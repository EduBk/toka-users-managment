import pytest

from domain.auth.exceptions import InvalidEmail
from domain.auth.value_objects import Email


def test_email_is_normalized() -> None:
    assert Email("  Ana.Perez@Example.COM ").value == "ana.perez@example.com"


@pytest.mark.parametrize(
    "value",
    ["", "ana", "ana@", "@example.com", "ana@example", "ana @example.com"],
)
def test_invalid_email_is_rejected(value: str) -> None:
    with pytest.raises(InvalidEmail):
        Email(value)


def test_email_longer_than_limit_is_rejected() -> None:
    value = f"{'a' * 250}@example.com"
    with pytest.raises(InvalidEmail):
        Email(value)
