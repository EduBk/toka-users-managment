"""Token revocation port, backed by Redis in production (E2.4)."""

from typing import Protocol


class TokenRevocationStore(Protocol):
    async def revoke(self, jti: str, ttl_seconds: int) -> None: ...

    async def is_revoked(self, jti: str) -> bool: ...
