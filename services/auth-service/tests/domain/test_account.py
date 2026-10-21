from datetime import timezone

import pytest

from domain.auth.entity import Account
from domain.auth.exceptions import InvalidAccount
from domain.auth.value_objects import Email


def test_create_sets_defaults() -> None:
    account = Account.create(
        email=Email("ana@example.com"), password_hash="hashed"
    )

    assert account.email.value == "ana@example.com"
    assert account.password_hash == "hashed"
    assert account.is_active is True
    assert account.created_at.tzinfo == timezone.utc
    assert account.id is not None


def test_create_requires_password_hash() -> None:
    with pytest.raises(InvalidAccount):
        Account.create(email=Email("ana@example.com"), password_hash="  ")
