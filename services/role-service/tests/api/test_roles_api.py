from uuid import uuid4

from fastapi.testclient import TestClient

from tests.api.conftest import AuthHeaders
from tests.application.fakes import FakeUnitOfWork

ADMIN = ("admin",)


def _create_role(
    client: TestClient,
    headers: dict[str, str],
    name: str = "support",
    permissions: list[str] | None = None,
) -> dict:
    response = client.post(
        "/roles",
        json={
            "name": name,
            "description": "Support agents",
            "permissions": permissions or ["users:read"],
        },
        headers=headers,
    )
    assert response.status_code == 201
    return response.json()


def test_admin_creates_a_role(
    client: TestClient, auth_headers: AuthHeaders
) -> None:
    body = _create_role(client, auth_headers(roles=ADMIN))

    assert body["name"] == "support"
    assert body["permissions"] == ["users:read"]


def test_create_role_requires_a_token(client: TestClient) -> None:
    response = client.post("/roles", json={"name": "support"})

    assert response.status_code == 401


def test_non_admin_cannot_create_roles(
    client: TestClient, auth_headers: AuthHeaders
) -> None:
    response = client.post(
        "/roles", json={"name": "support"}, headers=auth_headers(roles=("user",))
    )

    assert response.status_code == 403
    assert response.json()["code"] == "insufficient_role"


def test_duplicated_role_name_returns_409(
    client: TestClient, auth_headers: AuthHeaders
) -> None:
    headers = auth_headers(roles=ADMIN)
    _create_role(client, headers)

    response = client.post("/roles", json={"name": "Support"}, headers=headers)

    assert response.status_code == 409
    assert response.json()["code"] == "role_already_exists"


def test_invalid_permission_returns_400(
    client: TestClient, auth_headers: AuthHeaders
) -> None:
    response = client.post(
        "/roles",
        json={"name": "support", "permissions": ["users write"]},
        headers=auth_headers(roles=ADMIN),
    )

    assert response.status_code == 400
    assert response.json()["code"] == "invalid_permission_name"


def test_any_authenticated_account_lists_roles(
    client: TestClient, auth_headers: AuthHeaders
) -> None:
    _create_role(client, auth_headers(roles=ADMIN))

    response = client.get("/roles", headers=auth_headers())

    assert response.status_code == 200
    assert [role["name"] for role in response.json()] == ["support"]


def test_admin_replaces_role_permissions(
    client: TestClient, auth_headers: AuthHeaders
) -> None:
    headers = auth_headers(roles=ADMIN)
    role = _create_role(client, headers)

    response = client.put(
        f"/roles/{role['id']}/permissions",
        json={"permissions": ["ai:use", "users:read"]},
        headers=headers,
    )
    missing = client.put(
        f"/roles/{uuid4()}/permissions",
        json={"permissions": []},
        headers=headers,
    )

    assert response.status_code == 200
    assert response.json()["permissions"] == ["ai:use", "users:read"]
    assert missing.status_code == 404
    assert missing.json()["code"] == "role_not_found"


def test_assign_and_revoke_are_reflected_in_effective_permissions(
    client: TestClient, auth_headers: AuthHeaders, uow: FakeUnitOfWork
) -> None:
    headers = auth_headers(roles=ADMIN)
    reader = auth_headers(scopes=("roles:read",))
    role = _create_role(client, headers, permissions=["audit:read"])
    user_id = uuid4()

    assigned = client.post(
        f"/users/{user_id}/roles", json={"role_id": role["id"]}, headers=headers
    )
    roles = client.get(f"/users/{user_id}/roles", headers=reader)
    permissions = client.get(f"/users/{user_id}/permissions", headers=reader)
    revoked = client.delete(
        f"/users/{user_id}/roles/{role['id']}", headers=headers
    )
    after = client.get(f"/users/{user_id}/permissions", headers=reader)

    assert assigned.status_code == 204
    assert [item["name"] for item in roles.json()] == ["support"]
    assert permissions.json() == {
        "user_id": str(user_id),
        "permissions": ["audit:read"],
    }
    assert revoked.status_code == 204
    assert after.json()["permissions"] == []
    assert [type(event).__name__ for event, _ in uow.outbox.events] == [
        "RoleAssigned",
        "RoleRevoked",
    ]


def test_non_admin_cannot_assign_roles(
    client: TestClient, auth_headers: AuthHeaders
) -> None:
    response = client.post(
        f"/users/{uuid4()}/roles",
        json={"role_id": str(uuid4())},
        headers=auth_headers(roles=("auditor",)),
    )

    assert response.status_code == 403


def test_assigning_an_unknown_role_returns_404(
    client: TestClient, auth_headers: AuthHeaders
) -> None:
    response = client.post(
        f"/users/{uuid4()}/roles",
        json={"role_id": str(uuid4())},
        headers=auth_headers(roles=ADMIN),
    )

    assert response.status_code == 404


def test_invalid_path_ids_return_422(
    client: TestClient, auth_headers: AuthHeaders
) -> None:
    response = client.get(
        "/users/not-a-uuid/permissions",
        headers=auth_headers(scopes=("roles:read",)),
    )

    assert response.status_code == 422
    assert response.json()["code"] == "validation_error"


def test_user_access_reads_require_a_token(client: TestClient) -> None:
    for path in ("roles", "permissions"):
        response = client.get(f"/users/{uuid4()}/{path}")

        assert response.status_code == 401
        assert response.json()["code"] == "missing_token"


def test_user_access_reads_require_the_roles_read_scope(
    client: TestClient, auth_headers: AuthHeaders
) -> None:
    for path in ("roles", "permissions"):
        response = client.get(
            f"/users/{uuid4()}/{path}",
            headers=auth_headers(roles=("auditor",), scopes=("audit:read",)),
        )

        assert response.status_code == 403
        assert response.json()["code"] == "insufficient_scope"
