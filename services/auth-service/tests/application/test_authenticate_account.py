import pytest

from application.dto import AuthenticateAccountCommand
from application.exceptions import InvalidCredentials
from application.use_cases.authenticate_account import AuthenticateAccount
from domain.auth.entity import Account
from domain.auth.events import UserLoggedIn, UserLoginFailed
from domain.auth.value_objects import Email
from tests.application.fakes import (
    FakeEventOutbox,
    FakePasswordHasher,
    FakeTokenService,
    FakeUserAccessProvider,
    InMemoryAccountRepository,
)


@pytest.fixture
def repository() -> InMemoryAccountRepository:
    return InMemoryAccountRepository()


@pytest.fixture
def tokens() -> FakeTokenService:
    return FakeTokenService()


@pytest.fixture
def outbox() -> FakeEventOutbox:
    return FakeEventOutbox()


@pytest.fixture
def use_case(
    repository: InMemoryAccountRepository,
    tokens: FakeTokenService,
    outbox: FakeEventOutbox,
) -> AuthenticateAccount:
    return AuthenticateAccount(
        repository,
        FakePasswordHasher(),
        tokens,
        outbox,
        FakeUserAccessProvider(),
    )


async def _add_account(
    repository: InMemoryAccountRepository, *, is_active: bool = True
) -> Account:
    account = Account.create(
        email=Email("ana@example.com"), password_hash="hashed:secret"
    )
    account.is_active = is_active
    repository.accounts.append(account)
    return account


async def test_login_returns_the_account_and_a_token_pair(
    use_case: AuthenticateAccount,
    repository: InMemoryAccountRepository,
    outbox: FakeEventOutbox,
) -> None:
    account = await _add_account(repository)

    result = await use_case.execute(
        AuthenticateAccountCommand(
            email="ana@example.com",
            password="secret",
            correlation_id="req-1234",
        )
    )

    assert result.account == account
    assert result.access_token.token.startswith("access-")
    assert result.refresh_token.token.startswith("refresh-")
    assert result.access_token.expires_in > 0
    assert outbox.events == [
        (UserLoggedIn(user_id=account.id, email="ana@example.com"), "req-1234")
    ]


async def test_login_issues_roles_and_scopes_from_the_access_provider(
    repository: InMemoryAccountRepository,
    tokens: FakeTokenService,
) -> None:
    account = await _add_account(repository)
    access = FakeUserAccessProvider(
        roles=("admin",), scopes=("users:read", "users:write")
    )
    use_case = AuthenticateAccount(
        repository,
        FakePasswordHasher(),
        tokens,
        FakeEventOutbox(),
        access,
    )

    result = await use_case.execute(
        AuthenticateAccountCommand(
            email="ana@example.com",
            password="secret",
            correlation_id="req-1234",
        )
    )

    claims = tokens.decode(result.access_token.token)
    assert claims.roles == ("admin",)
    assert claims.scopes == ("users:read", "users:write")
    assert access.requested == [account.id]


async def test_login_rejects_a_wrong_password(
    use_case: AuthenticateAccount,
    repository: InMemoryAccountRepository,
    outbox: FakeEventOutbox,
) -> None:
    await _add_account(repository)

    with pytest.raises(InvalidCredentials):
        await use_case.execute(
            AuthenticateAccountCommand(
                email="ana@example.com",
                password="wrong",
                correlation_id="req-1234",
            )
        )

    assert outbox.events == [
        (
            UserLoginFailed(
                email="ana@example.com", reason="invalid_credentials"
            ),
            "req-1234",
        )
    ]


async def test_login_rejects_an_unknown_email(
    use_case: AuthenticateAccount, outbox: FakeEventOutbox
) -> None:
    with pytest.raises(InvalidCredentials):
        await use_case.execute(
            AuthenticateAccountCommand(
                email="  Nobody@Example.com ",
                password="secret",
                correlation_id="req-1234",
            )
        )

    assert outbox.events == [
        (
            UserLoginFailed(
                email="nobody@example.com", reason="invalid_credentials"
            ),
            "req-1234",
        )
    ]


async def test_login_rejects_an_inactive_account(
    use_case: AuthenticateAccount,
    repository: InMemoryAccountRepository,
    outbox: FakeEventOutbox,
) -> None:
    await _add_account(repository, is_active=False)

    with pytest.raises(InvalidCredentials):
        await use_case.execute(
            AuthenticateAccountCommand(
                email="ana@example.com",
                password="secret",
                correlation_id="req-1234",
            )
        )

    assert outbox.events == [
        (
            UserLoginFailed(
                email="ana@example.com", reason="invalid_credentials"
            ),
            "req-1234",
        )
    ]
