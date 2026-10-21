from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from api.deps import (
    get_authenticate_account,
    get_find_account_by_email,
    get_logout,
    get_refresh_tokens,
    get_register_account,
)
from api.errors import register_auth_exception_handlers
from api.jwks import router as jwks_router
from api.router import router
from app_common.app import create_service_app
from app_common.config import BaseServiceSettings
from app_common.jwt_auth import JwtValidator
from app_common.testing import TEST_AUDIENCE, TEST_ISSUER, generate_rsa_key_pair
from application.use_cases.authenticate_account import AuthenticateAccount
from application.use_cases.find_account_by_email import FindAccountByEmail
from application.use_cases.logout import Logout
from application.use_cases.refresh_tokens import RefreshTokens
from application.use_cases.register_account import RegisterAccount
from infrastructure.security.jwks import build_jwks
from infrastructure.security.rs256_token_service import Rs256TokenService
from tests.application.fakes import (
    FakeEventOutbox,
    FakePasswordHasher,
    FakeTokenRevocationStore,
    FakeUserAccessProvider,
    InMemoryAccountRepository,
)


@pytest.fixture(scope="session")
def key_pair() -> tuple[str, str]:
    return generate_rsa_key_pair()


@pytest.fixture
def accounts() -> InMemoryAccountRepository:
    return InMemoryAccountRepository()


@pytest.fixture
def outbox() -> FakeEventOutbox:
    return FakeEventOutbox()


@pytest.fixture
def revocations() -> FakeTokenRevocationStore:
    return FakeTokenRevocationStore()


@pytest.fixture
def client(
    key_pair: tuple[str, str],
    accounts: InMemoryAccountRepository,
    outbox: FakeEventOutbox,
    revocations: FakeTokenRevocationStore,
) -> Iterator[TestClient]:
    private_pem, public_pem = key_pair
    tokens = Rs256TokenService(
        private_key_pem=private_pem,
        public_key_pem=public_pem,
        issuer=TEST_ISSUER,
        audience=TEST_AUDIENCE,
        access_token_ttl_seconds=900,
        refresh_token_ttl_days=7,
    )
    hasher = FakePasswordHasher()
    access = FakeUserAccessProvider(roles=("admin",), scopes=("users:read",))

    app = create_service_app(
        BaseServiceSettings(service_name="auth-service"),
        routers=[router, jwks_router],
    )
    register_auth_exception_handlers(app)
    app.state.jwks = build_jwks(public_pem)
    app.state.jwt_validator = JwtValidator(
        issuer=TEST_ISSUER,
        audience=TEST_AUDIENCE,
        public_key=public_pem,
        revocation=revocations,
    )
    app.dependency_overrides[get_register_account] = lambda: RegisterAccount(
        accounts=accounts, password_hasher=hasher
    )
    app.dependency_overrides[get_authenticate_account] = lambda: (
        AuthenticateAccount(accounts, hasher, tokens, outbox, access)
    )
    app.dependency_overrides[get_refresh_tokens] = lambda: RefreshTokens(
        accounts, tokens, revocations, access
    )
    app.dependency_overrides[get_logout] = lambda: Logout(tokens, revocations)
    app.dependency_overrides[get_find_account_by_email] = lambda: (
        FindAccountByEmail(accounts)
    )

    with TestClient(app) as test_client:
        yield test_client
