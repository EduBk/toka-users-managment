import httpx
import pytest

from application.ports.user_access import UserAccess
from infrastructure.role_service.client import (
    HttpUserAccessProvider,
    NullUserAccessProvider,
)


def _transport(handler) -> httpx.MockTransport:
    return httpx.MockTransport(handler)


async def test_provider_returns_sorted_roles_and_permissions() -> None:
    user_id = "3f1c3d3e-4a1a-4b8a-9c3a-1d2e3f4a5b6c"

    authorizations: list[str | None] = []

    def handler(request: httpx.Request) -> httpx.Response:
        authorizations.append(request.headers.get("Authorization"))
        if request.url.path.endswith("/roles"):
            return httpx.Response(
                200,
                json=[{"name": "user"}, {"name": "admin"}],
                request=request,
            )
        return httpx.Response(
            200,
            json={
                "user_id": user_id,
                "permissions": ["users:write", "users:read"],
            },
            request=request,
        )

    provider = HttpUserAccessProvider(
        "http://role-service:8000",
        service_token=lambda: "service-token",
        transport=_transport(handler),
    )
    try:
        access = await provider.access_for(user_id)
    finally:
        await provider.close()

    assert access == UserAccess(
        roles=("admin", "user"),
        scopes=("users:read", "users:write"),
    )
    assert authorizations == ["Bearer service-token", "Bearer service-token"]


@pytest.mark.parametrize("failure_path", ["/roles", "/permissions"])
async def test_provider_fails_open_to_empty_access(failure_path: str) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith(failure_path):
            return httpx.Response(503, request=request)
        if request.url.path.endswith("/roles"):
            return httpx.Response(200, json=[], request=request)
        return httpx.Response(
            200, json={"permissions": []}, request=request
        )

    provider = HttpUserAccessProvider(
        "http://role-service:8000",
        service_token=lambda: "service-token",
        transport=_transport(handler),
    )
    try:
        access = await provider.access_for(
            "3f1c3d3e-4a1a-4b8a-9c3a-1d2e3f4a5b6c"
        )
    finally:
        await provider.close()

    assert access == UserAccess()


async def test_null_provider_returns_no_access() -> None:
    access = await NullUserAccessProvider().access_for(
        "3f1c3d3e-4a1a-4b8a-9c3a-1d2e3f4a5b6c"
    )

    assert access == UserAccess()
