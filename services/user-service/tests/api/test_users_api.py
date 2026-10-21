from uuid import uuid4

from fastapi.testclient import TestClient

from tests.api.conftest import AuthHeaders
from tests.application.fakes import FakeUnitOfWork

READ = ("users:read",)
WRITE = ("users:read", "users:write")


def _create(
    client: TestClient, headers: dict[str, str], email: str = "ana@example.com"
) -> dict:
    response = client.post(
        "/users",
        json={"email": email, "name": "Ana Perez", "profile": {"team": "sales"}},
        headers=headers,
    )
    assert response.status_code == 201
    return response.json()


def test_create_user_returns_201_and_the_user(
    client: TestClient, auth_headers: AuthHeaders, uow: FakeUnitOfWork
) -> None:
    body = _create(client, auth_headers(scopes=WRITE))

    assert body["email"] == "ana@example.com"
    assert body["status"] == "active"
    assert body["profile"] == {"team": "sales"}
    assert len(uow.users.users) == 1
    assert len(uow.outbox.events) == 1


def test_requests_without_token_are_rejected_with_401(client: TestClient) -> None:
    response = client.get("/users")

    assert response.status_code == 401
    assert response.json()["code"] == "missing_token"


def test_an_invalid_token_is_rejected_with_401(client: TestClient) -> None:
    response = client.get(
        "/users", headers={"Authorization": "Bearer not-a-jwt"}
    )

    assert response.status_code == 401
    assert response.json()["code"] == "invalid_token"


def test_writes_without_users_write_scope_are_forbidden(
    client: TestClient, auth_headers: AuthHeaders
) -> None:
    response = client.post(
        "/users",
        json={"email": "ana@example.com", "name": "Ana"},
        headers=auth_headers(scopes=READ),
    )

    assert response.status_code == 403
    assert response.json()["code"] == "insufficient_scope"


def test_invalid_payload_returns_422_with_the_error_schema(
    client: TestClient, auth_headers: AuthHeaders
) -> None:
    response = client.post(
        "/users", json={"name": ""}, headers=auth_headers(scopes=WRITE)
    )

    assert response.status_code == 422
    assert response.json()["code"] == "validation_error"


def test_invalid_email_returns_400(
    client: TestClient, auth_headers: AuthHeaders
) -> None:
    response = client.post(
        "/users",
        json={"email": "not-an-email", "name": "Ana"},
        headers=auth_headers(scopes=WRITE),
    )

    assert response.status_code == 400
    assert response.json()["code"] == "invalid_email"


def test_duplicated_email_returns_409(
    client: TestClient, auth_headers: AuthHeaders
) -> None:
    headers = auth_headers(scopes=WRITE)
    _create(client, headers)

    response = client.post(
        "/users",
        json={"email": "ana@example.com", "name": "Other"},
        headers=headers,
    )

    assert response.status_code == 409
    assert response.json()["code"] == "email_already_exists"


def test_list_users_paginates(
    client: TestClient, auth_headers: AuthHeaders
) -> None:
    headers = auth_headers(scopes=WRITE)
    for index in range(3):
        _create(client, headers, email=f"user{index}@example.com")

    response = client.get(
        "/users?page=1&page_size=2", headers=auth_headers(scopes=READ)
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 3
    assert body["page_size"] == 2
    assert len(body["items"]) == 2


def test_list_users_rejects_a_page_size_over_100(
    client: TestClient, auth_headers: AuthHeaders
) -> None:
    response = client.get(
        "/users?page_size=101", headers=auth_headers(scopes=READ)
    )

    assert response.status_code == 422


def test_get_user_returns_the_user_or_404(
    client: TestClient, auth_headers: AuthHeaders
) -> None:
    created = _create(client, auth_headers(scopes=WRITE))
    headers = auth_headers(scopes=READ)

    found = client.get(f"/users/{created['id']}", headers=headers)
    missing = client.get(f"/users/{uuid4()}", headers=headers)

    assert found.status_code == 200
    assert found.json()["id"] == created["id"]
    assert missing.status_code == 404
    assert missing.json()["code"] == "user_not_found"


def test_patch_updates_the_user(
    client: TestClient, auth_headers: AuthHeaders
) -> None:
    headers = auth_headers(scopes=WRITE)
    created = _create(client, headers)

    response = client.patch(
        f"/users/{created['id']}", json={"name": "Ana Maria"}, headers=headers
    )

    assert response.status_code == 200
    assert response.json()["name"] == "Ana Maria"


def test_patch_without_fields_returns_422(
    client: TestClient, auth_headers: AuthHeaders
) -> None:
    headers = auth_headers(scopes=WRITE)
    created = _create(client, headers)

    response = client.patch(f"/users/{created['id']}", json={}, headers=headers)

    assert response.status_code == 422


def test_delete_deactivates_the_user_idempotently(
    client: TestClient, auth_headers: AuthHeaders
) -> None:
    headers = auth_headers(scopes=WRITE)
    created = _create(client, headers)

    first = client.delete(f"/users/{created['id']}", headers=headers)
    second = client.delete(f"/users/{created['id']}", headers=headers)
    fetched = client.get(f"/users/{created['id']}", headers=headers)

    assert first.status_code == 204
    assert second.status_code == 204
    assert fetched.json()["status"] == "inactive"


def test_responses_carry_the_request_id(
    client: TestClient, auth_headers: AuthHeaders
) -> None:
    response = client.get(
        "/users",
        headers={**auth_headers(scopes=READ), "X-Request-ID": "trace-12345"},
    )

    assert response.headers["X-Request-ID"] == "trace-12345"
