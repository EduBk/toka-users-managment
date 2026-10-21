"""Read-only access to system data owned by other microservices (E5.3)."""

from __future__ import annotations

from typing import Protocol


class SystemDataProvider(Protocol):
    async def describe(self, bearer_token: str) -> str | None:
        """Return a short, PII-free summary of users and roles, or ``None``."""
