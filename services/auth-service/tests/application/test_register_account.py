import pytest

from application.dto import RegisterAccountCommand
from application.use_cases.register_account import RegisterAccount
from domain.auth.entity import Account
from domain.auth.exceptions import EmailAlreadyRegistered, InvalidEmail
from domain.auth.value_objects import Email
from tests.application.fakes import FakePasswordHasher, InMemoryAccountRepository


@pytest.fixture
def repository() -> InMemoryAccountRepository:
    return InMemoryAccountRepository()


@pytest.fixture
def use_case(repository: InMemoryAccountRepository) -> RegisterAccount:
    return RegisterAccount(repository, FakePasswordHasher())


async def test_register_stores_a_hashed_password(
    use_case: RegisterAccount, repository: InMemoryAccountRepository
) -> None:
    account = await use_case.execute(
        RegisterAccountCommand(email="Ana@Example.com", password="secret")
    )

    assert account.email.value == "ana@example.com"
    assert account.password_hash == "hashed:secret"
    assert account.password_hash != "secret"
    assert repository.accounts == [account]


async def test_register_normalizes_the_email(
    use_case: RegisterAccount, repository: InMemoryAccountRepository
) -> None:
    await use_case.execute(
        RegisterAccountCommand(email="  ANA@example.com ", password="secret")
    )

    assert repository.accounts[0].email == Email("ana@example.com")


async def test_register_rejects_a_duplicated_email(
    use_case: RegisterAccount, repository: InMemoryAccountRepository
) -> None:
    repository.accounts.append(
        Account.create(email=Email("ana@example.com"), password_hash="hashed:x")
    )

    with pytest.raises(EmailAlreadyRegistered):
        await use_case.execute(
            RegisterAccountCommand(email="ana@example.com", password="secret")
        )


async def test_register_rejects_an_invalid_email(use_case: RegisterAccount) -> None:
    with pytest.raises(InvalidEmail):
        await use_case.execute(
            RegisterAccountCommand(email="not-an-email", password="secret")
        )
