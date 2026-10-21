"""HTTP client that resolves roles and scopes from ``role-service``.

Login and refresh call the read endpoints of the roles context with a
short-lived service token (scope ``roles:read``). The dependency is soft: if the service is unavailable, the caller gets no roles and
no scopes (least privilege) and the failure is logged, so authentication keeps
working.
"""

import logging
from collections.abc import Callable
from uuid import UUID

import httpx

from application.ports.user_access import UserAccess
from app_common.logging import log_event

logger = logging.getLogger("auth.role_service")


class HttpUserAccessProvider:
    def __init__(
        self,
        base_url: str,
        *,
        service_token: Callable[[], str],
        timeout_seconds: float = 2.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._service_token = service_token
        self._client = httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            timeout=timeout_seconds,
            transport=transport,
        )

    async def access_for(self, user_id: UUID) -> UserAccess:
        try:
            headers = {"Authorization": f"Bearer {self._service_token()}"}
            roles_response = await self._client.get(
                f"/users/{user_id}/roles", headers=headers
            )
            roles_response.raise_for_status()
            permissions_response = await self._client.get(
                f"/users/{user_id}/permissions", headers=headers
            )
            permissions_response.raise_for_status()

            roles = tuple(
                sorted(
                    {
                        str(item["name"])
                        for item in roles_response.json()
                    }
                )
            )
            scopes = tuple(
                sorted(
                    {
                        str(permission)
                        for permission in permissions_response.json()[
                            "permissions"
                        ]
                    }
                )
            )
            return UserAccess(roles=roles, scopes=scopes)
        except (httpx.HTTPError, KeyError, TypeError, ValueError) as exc:
            log_event(
                logger,
                logging.WARNING,
                "role_service_unavailable",
                user_id=str(user_id),
                reason=f"{type(exc).__name__}: {exc}",
            )
            return UserAccess()

    async def close(self) -> None:
        await self._client.aclose()


class NullUserAccessProvider:
    """Used when no role service is configured: tokens carry no authorization."""

    async def access_for(self, user_id: UUID) -> UserAccess:
        return UserAccess()

    async def close(self) -> None:
        return None
