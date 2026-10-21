from collections.abc import Callable, Iterator

import pytest
from fastapi.testclient import TestClient

from api.router import router
from app_common.app import create_service_app
from app_common.config import BaseServiceSettings
from app_common.jwt_auth import JwtValidator
from app_common.testing import (
    TEST_AUDIENCE,
    TEST_ISSUER,
    bearer,
    generate_rsa_key_pair,
    issue_access_token,
)
from tests.application.fakes import InMemoryAuditEntryRepository

AuthHeaders = Callable[..., dict[str, str]]


@pytest.fixture(scope="session")
def key_pair() -> tuple[str, str]:
    return generate_rsa_key_pair()


@pytest.fixture
def auth_headers(key_pair: tuple[str, str]) -> AuthHeaders:
    def build(*, roles: tuple[str, ...] = ()) -> dict[str, str]:
        return bearer(issue_access_token(key_pair[0], roles=roles))

    return build


@pytest.fixture
def repository() -> InMemoryAuditEntryRepository:
    return InMemoryAuditEntryRepository()


@pytest.fixture
def client(
    key_pair: tuple[str, str], repository: InMemoryAuditEntryRepository
) -> Iterator[TestClient]:
    app = create_service_app(
        BaseServiceSettings(service_name="audit-service"), routers=[router]
    )
    app.state.audit_repository = repository
    app.state.jwt_validator = JwtValidator(
        issuer=TEST_ISSUER, audience=TEST_AUDIENCE, public_key=key_pair[1]
    )
    with TestClient(app) as test_client:
        yield test_client
