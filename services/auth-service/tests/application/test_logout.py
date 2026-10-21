from uuid import uuid4

import pytest

from application.dto import LogoutCommand
from application.exceptions import InvalidToken
from application.use_cases.logout import Logout
from domain.auth.entity import Account
from domain.auth.value_objects import Email, TokenClaims
from tests.application.fakes import (
    FakeTokenRevocationStore,
    FakeTokenService,
    InMemoryAccountRepository,
)


@pytest.fixture
def tokens() -> FakeTokenService:
    return FakeTokenService()


@pytest.fixture
def revocations() -> FakeTokenRevocationStore:
    return FakeTokenRevocationStore()


@pytest.fixture
def use_case(
    tokens: FakeTokenService, revocations: FakeTokenRevocationStore
) -> Logout:
    return Logout(tokens, revocations)


@pytest.fixture
def account() -> Account:
    return Account.create(
        email=Email("ana@example.com"), password_hash="hashed:secret"
    )


async def test_logout_revokes_the_access_and_refresh_tokens(
    use_case: Logout,
    tokens: FakeTokenService,
    revocations: FakeTokenRevocationStore,
    account: Account,
) -> None:
    access = tokens.issue_access_token(account)
    refresh = tokens.issue_refresh_token(account)
    access_claims = tokens.decode(access.token)

    await use_case.execute(
        LogoutCommand(
            refresh_token=refresh.token, access_claims=access_claims
        )
    )

    assert access.jti in revocations.revoked
    assert refresh.jti in revocations.revoked


async def test_logout_rejects_a_refresh_token_from_another_subject(
    use_case: Logout,
    tokens: FakeTokenService,
    account: Account,
) -> None:
    access_claims = tokens.decode(tokens.issue_access_token(account).token)
    other_refresh = tokens.register(
        TokenClaims(
            sub=str(uuid4()),
            email="other@example.com",
            roles=(),
            scopes=(),
            issuer="auth-service",
            audience="user-management",
            expires_at=4_102_444_800,
            jti=str(uuid4()),
            token_type="refresh",
        )
    )

    with pytest.raises(InvalidToken):
        await use_case.execute(
            LogoutCommand(
                refresh_token=other_refresh, access_claims=access_claims
            )
        )


async def test_logout_rejects_an_access_token_as_refresh(
    use_case: Logout,
    tokens: FakeTokenService,
    account: Account,
) -> None:
    access = tokens.issue_access_token(account)
    access_claims = tokens.decode(access.token)

    with pytest.raises(InvalidToken):
        await use_case.execute(
            LogoutCommand(refresh_token=access.token, access_claims=access_claims)
        )


async def test_logout_rejects_an_unknown_refresh_token(
    use_case: Logout,
    tokens: FakeTokenService,
    account: Account,
) -> None:
    access_claims = tokens.decode(tokens.issue_access_token(account).token)

    with pytest.raises(InvalidToken):
        await use_case.execute(
            LogoutCommand(
                refresh_token="not-a-token", access_claims=access_claims
            )
        )
