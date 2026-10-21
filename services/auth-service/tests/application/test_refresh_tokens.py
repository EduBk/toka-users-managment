from uuid import uuid4

import pytest

from application.dto import RefreshTokensCommand
from application.exceptions import InvalidToken
from application.use_cases.refresh_tokens import RefreshTokens
from domain.auth.entity import Account
from domain.auth.value_objects import Email, TokenClaims
from tests.application.fakes import (
    FakeTokenRevocationStore,
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
def revocations() -> FakeTokenRevocationStore:
    return FakeTokenRevocationStore()


@pytest.fixture
def use_case(
    repository: InMemoryAccountRepository,
    tokens: FakeTokenService,
    revocations: FakeTokenRevocationStore,
) -> RefreshTokens:
    return RefreshTokens(
        repository, tokens, revocations, FakeUserAccessProvider()
    )


@pytest.fixture
def account(repository: InMemoryAccountRepository) -> Account:
    account = Account.create(
        email=Email("ana@example.com"), password_hash="hashed:secret"
    )
    repository.accounts.append(account)
    return account


def _refresh_claims(
    account: Account, *, sub: str | None = None
) -> TokenClaims:
    return TokenClaims(
        sub=sub or str(account.id),
        email=account.email.value,
        roles=(),
        scopes=(),
        issuer="auth-service",
        audience="user-management",
        expires_at=4_102_444_800,
        jti=str(uuid4()),
        token_type="refresh",
    )


async def test_refresh_rotates_the_token_and_revokes_the_old_one(
    use_case: RefreshTokens,
    tokens: FakeTokenService,
    revocations: FakeTokenRevocationStore,
    account: Account,
) -> None:
    old_refresh = tokens.issue_refresh_token(account)

    result = await use_case.execute(
        RefreshTokensCommand(refresh_token=old_refresh.token)
    )

    assert result.account == account
    assert result.access_token.token.startswith("access-")
    assert result.refresh_token.jti != old_refresh.jti
    assert old_refresh.jti in revocations.revoked
    assert revocations.revoked[old_refresh.jti] > 0


async def test_refresh_keeps_roles_and_scopes_in_the_new_access_token(
    repository: InMemoryAccountRepository,
    tokens: FakeTokenService,
    revocations: FakeTokenRevocationStore,
    account: Account,
) -> None:
    refresh = tokens.issue_refresh_token(account)
    access = FakeUserAccessProvider(
        roles=("auditor",), scopes=("audit:read",)
    )
    use_case = RefreshTokens(repository, tokens, revocations, access)

    result = await use_case.execute(
        RefreshTokensCommand(refresh_token=refresh.token)
    )

    claims = tokens.decode(result.access_token.token)
    assert claims.roles == ("auditor",)
    assert claims.scopes == ("audit:read",)
    assert access.requested == [account.id]


async def test_refresh_rejects_an_already_revoked_token(
    use_case: RefreshTokens,
    tokens: FakeTokenService,
    revocations: FakeTokenRevocationStore,
    account: Account,
) -> None:
    refresh = tokens.issue_refresh_token(account)
    await revocations.revoke(refresh.jti, 900)

    with pytest.raises(InvalidToken):
        await use_case.execute(RefreshTokensCommand(refresh_token=refresh.token))


async def test_refresh_rejects_an_access_token(
    use_case: RefreshTokens,
    tokens: FakeTokenService,
    account: Account,
) -> None:
    access = tokens.issue_access_token(account)

    with pytest.raises(InvalidToken):
        await use_case.execute(RefreshTokensCommand(refresh_token=access.token))


async def test_refresh_rejects_an_unknown_account(
    use_case: RefreshTokens,
    tokens: FakeTokenService,
    account: Account,
) -> None:
    token = tokens.register(_refresh_claims(account, sub=str(uuid4())))

    with pytest.raises(InvalidToken):
        await use_case.execute(RefreshTokensCommand(refresh_token=token))


async def test_refresh_rejects_an_inactive_account(
    use_case: RefreshTokens,
    tokens: FakeTokenService,
    account: Account,
) -> None:
    refresh = tokens.issue_refresh_token(account)
    account.is_active = False

    with pytest.raises(InvalidToken):
        await use_case.execute(RefreshTokensCommand(refresh_token=refresh.token))
