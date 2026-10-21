import pytest

from application.exceptions import AccountNotFound
from application.use_cases.find_account_by_email import FindAccountByEmail
from domain.auth.entity import Account
from domain.auth.exceptions import InvalidEmail
from domain.auth.value_objects import Email
from tests.application.fakes import InMemoryAccountRepository


async def test_find_account_normalizes_the_email() -> None:
    repository = InMemoryAccountRepository()
    account = Account.create(email=Email("ana@example.com"), password_hash="h")
    repository.accounts.append(account)

    found = await FindAccountByEmail(repository).execute(" ANA@example.com ")

    assert found == account


async def test_find_account_raises_when_missing() -> None:
    with pytest.raises(AccountNotFound):
        await FindAccountByEmail(InMemoryAccountRepository()).execute(
            "nobody@example.com"
        )


async def test_find_account_rejects_invalid_emails() -> None:
    with pytest.raises(InvalidEmail):
        await FindAccountByEmail(InMemoryAccountRepository()).execute("nope")
