import pytest
from fastapi.testclient import TestClient

from app_common.rate_limit import InMemoryRateLimiter, RateLimitPolicy, RateLimitRule
from app_common.testing import bearer, issue_access_token
from tests.application.fakes import FakeEventOutbox, FakeTokenRevocationStore

CREDENTIALS = {"email": "ana@example.com", "password": "s3cret-pass"}


def _register(client: TestClient) -> dict:
    response = client.post("/auth/register", json=CREDENTIALS)
    assert response.status_code == 201
    return response.json()


def _login(client: TestClient) -> dict:
    _register(client)
    response = client.post("/auth/login", json=CREDENTIALS)
    assert response.status_code == 200
    return response.json()


def test_register_returns_201_without_the_password_hash(
    client: TestClient,
) -> None:
    body = _register(client)

    assert body["email"] == "ana@example.com"
    assert body["is_active"] is True
    assert "password_hash" not in body


def test_register_rejects_a_duplicated_email(client: TestClient) -> None:
    _register(client)

    response = client.post("/auth/register", json=CREDENTIALS)

    assert response.status_code == 409
    assert response.json()["code"] == "email_already_registered"


def test_register_rejects_an_invalid_email(client: TestClient) -> None:
    response = client.post(
        "/auth/register", json={"email": "nope", "password": "secret"}
    )

    assert response.status_code == 400
    assert response.json()["code"] == "invalid_email"


def test_register_rejects_passwords_over_72_bytes(client: TestClient) -> None:
    response = client.post(
        "/auth/register",
        json={"email": "ana@example.com", "password": "ñ" * 40},
    )

    assert response.status_code == 422
    assert response.json()["code"] == "validation_error"


def test_login_issues_a_bearer_token_pair(
    client: TestClient, outbox: FakeEventOutbox
) -> None:
    body = _login(client)

    assert body["token_type"] == "bearer"
    assert body["expires_in"] == 900
    assert body["access_token"] and body["refresh_token"]
    assert [type(event).__name__ for event, _ in outbox.events] == [
        "UserLoggedIn"
    ]


def test_login_with_wrong_password_returns_401(
    client: TestClient, outbox: FakeEventOutbox
) -> None:
    _register(client)

    response = client.post(
        "/auth/login", json={**CREDENTIALS, "password": "wrong"}
    )

    assert response.status_code == 401
    assert response.json()["code"] == "invalid_credentials"
    assert [type(event).__name__ for event, _ in outbox.events] == [
        "UserLoginFailed"
    ]


def test_refresh_rotates_the_pair_and_revokes_the_old_refresh_token(
    client: TestClient,
) -> None:
    tokens = _login(client)

    rotated = client.post(
        "/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
    )
    replayed = client.post(
        "/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
    )

    assert rotated.status_code == 200
    assert rotated.json()["refresh_token"] != tokens["refresh_token"]
    assert replayed.status_code == 401
    assert replayed.json()["code"] == "invalid_token"


def test_refresh_rejects_an_access_token(client: TestClient) -> None:
    tokens = _login(client)

    response = client.post(
        "/auth/refresh", json={"refresh_token": tokens["access_token"]}
    )

    assert response.status_code == 401


def test_logout_revokes_both_tokens(
    client: TestClient, revocations: FakeTokenRevocationStore
) -> None:
    tokens = _login(client)
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    response = client.post(
        "/auth/logout",
        json={"refresh_token": tokens["refresh_token"]},
        headers=headers,
    )
    reused = client.post(
        "/auth/logout",
        json={"refresh_token": tokens["refresh_token"]},
        headers=headers,
    )

    assert response.status_code == 204
    assert len(revocations.revoked) == 2
    assert reused.status_code == 401


@pytest.mark.parametrize(
    "headers", [{}, {"Authorization": "Bearer garbage"}]
)
def test_logout_requires_a_valid_access_token(
    client: TestClient, headers: dict[str, str]
) -> None:
    response = client.post(
        "/auth/logout", json={"refresh_token": "x"}, headers=headers
    )

    assert response.status_code == 401


def test_jwks_publishes_the_rs256_public_key(client: TestClient) -> None:
    response = client.get("/.well-known/jwks.json")

    key = response.json()["keys"][0]
    assert key["kty"] == "RSA"
    assert key["alg"] == "RS256"
    assert key["kid"]


def test_admin_finds_an_account_by_email(
    client: TestClient, key_pair: tuple[str, str]
) -> None:
    registered = _register(client)
    admin = bearer(issue_access_token(key_pair[0], roles=("admin",)))

    found = client.get(
        "/auth/accounts", params={"email": " Ana@Example.com "}, headers=admin
    )
    missing = client.get(
        "/auth/accounts", params={"email": "nobody@example.com"}, headers=admin
    )

    assert found.status_code == 200
    assert found.json()["id"] == registered["id"]
    assert "password_hash" not in found.json()
    assert missing.status_code == 404
    assert missing.json()["code"] == "account_not_found"


def test_account_lookup_requires_the_admin_role(
    client: TestClient, key_pair: tuple[str, str]
) -> None:
    user = bearer(issue_access_token(key_pair[0], roles=("user",)))

    anonymous = client.get("/auth/accounts", params={"email": "a@example.com"})
    forbidden = client.get(
        "/auth/accounts", params={"email": "a@example.com"}, headers=user
    )

    assert anonymous.status_code == 401
    assert forbidden.status_code == 403


def test_login_is_rate_limited_per_client(client: TestClient) -> None:
    client.app.state.rate_limit = RateLimitPolicy(  # type: ignore[attr-defined]
        InMemoryRateLimiter(), RateLimitRule(limit=2, window_seconds=60)
    )
    _register(client)

    statuses = [
        client.post("/auth/login", json=CREDENTIALS).status_code for _ in range(3)
    ]

    assert statuses == [200, 200, 429]


def test_health_reports_the_service(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["service"] == "auth-service"
