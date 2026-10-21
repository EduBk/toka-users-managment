"""Read-only summary of users and roles for the agent (E5.3).

The caller's access token is forwarded, so the existing authorization of
``user-service`` and ``role-service`` still applies: if the user cannot read
users, the summary is simply omitted. Only aggregates and role names are sent
to the LLM; emails and names never leave the services.
"""

from __future__ import annotations

import logging
from collections import Counter

import httpx

from app_common.logging import log_event

logger = logging.getLogger("ai_service.system_data")


class HttpSystemDataProvider:
    def __init__(
        self,
        *,
        user_service_url: str,
        role_service_url: str,
        timeout_seconds: float = 2.0,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._user_service_url = user_service_url.rstrip("/")
        self._role_service_url = role_service_url.rstrip("/")
        self._client = client or httpx.AsyncClient(timeout=timeout_seconds)

    async def describe(self, bearer_token: str) -> str | None:
        headers = {"Authorization": f"Bearer {bearer_token}"}
        users = await self._get(
            f"{self._user_service_url}/users",
            headers=headers,
            params={"page_size": 100},
        )
        roles = await self._get(f"{self._role_service_url}/roles", headers=headers)
        if users is None and roles is None:
            return None

        lines: list[str] = []
        if users is not None:
            items = users.get("items", []) if isinstance(users, dict) else []
            statuses = Counter(item.get("status", "unknown") for item in items)
            summary = ", ".join(
                f"{status}={count}" for status, count in sorted(statuses.items())
            )
            lines.append(
                f"user-service: {users.get('total', len(items))} usuarios "
                f"(muestra de {len(items)}): {summary}"
            )
        if roles is not None:
            entries = roles if isinstance(roles, list) else roles.get("items", [])
            names = sorted(
                str(role.get("name", "")) for role in entries if isinstance(role, dict)
            )
            lines.append(
                "role-service: roles disponibles: "
                + (", ".join(name for name in names if name) or "ninguno")
            )
        return "\n".join(lines) if lines else None

    async def _get(
        self, url: str, *, headers: dict[str, str], params: dict[str, int] | None = None
    ) -> dict | list | None:
        try:
            response = await self._client.get(url, headers=headers, params=params)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            log_event(
                logger,
                logging.WARNING,
                "system_data_unavailable",
                service=url.split("/")[2] if "://" in url else url,
                error=type(exc).__name__,
            )
            return None
        return response.json()

    async def aclose(self) -> None:
        await self._client.aclose()
