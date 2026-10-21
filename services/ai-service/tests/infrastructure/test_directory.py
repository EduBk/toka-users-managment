import httpx
import pytest

from infrastructure.directory.http_directory import HttpSystemDataProvider

USERS_URL = "http://user-service:8000"
ROLES_URL = "http://role-service:8000"


def _provider(handler: httpx.MockTransport) -> HttpSystemDataProvider:
    client = httpx.AsyncClient(transport=handler)
    return HttpSystemDataProvider(
        user_service_url=USERS_URL,
        role_service_url=ROLES_URL,
        client=client,
    )


def _ok_handler(request: httpx.Request) -> httpx.Response:
    if request.url.path == "/users":
        assert request.headers["authorization"] == "Bearer token"
        return httpx.Response(
            200,
            json={
                "items": [
                    {"email": "ana@example.com", "status": "active"},
                    {"email": "luis@example.com", "status": "inactive"},
                    {"email": "eva@example.com", "status": "active"},
                ],
                "total": 3,
            },
        )
    return httpx.Response(
        200,
        json=[
            {"name": "admin", "permissions": ["users:write"]},
            {"name": "auditor", "permissions": ["audit:read"]},
        ],
    )


async def test_describe_summarises_users_and_roles_without_pii() -> None:
    provider = _provider(httpx.MockTransport(_ok_handler))

    description = await provider.describe("token")

    assert description is not None
    assert "user-service: 3 usuarios" in description
    assert "active=2" in description
    assert "inactive=1" in description
    assert "admin, auditor" in description
    assert "ana@example.com" not in description
    await provider.aclose()


async def test_describe_uses_the_available_service_when_the_other_fails() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/users":
            return httpx.Response(403, json={"code": "insufficient_scope"})
        return httpx.Response(200, json=[{"name": "admin"}])

    provider = _provider(httpx.MockTransport(handler))

    description = await provider.describe("token")

    assert description is not None
    assert "role-service: roles disponibles: admin" in description
    await provider.aclose()


async def test_describe_returns_none_when_every_service_fails() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("down", request=request)

    provider = _provider(httpx.MockTransport(handler))

    assert await provider.describe("token") is None
    await provider.aclose()


async def test_provider_closes_its_client() -> None:
    provider = _provider(httpx.MockTransport(_ok_handler))
    await provider.aclose()

    with pytest.raises(RuntimeError):
        await provider.describe("token")
