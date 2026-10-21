"""Redis implementation of :class:`TokenRevocationStore`.

Revoked token ids are kept only for the lifetime of the token, so Redis expires
them automatically (E2.4).
"""

from redis.asyncio import Redis

_KEY_PREFIX = "auth:revoked:"


class RedisTokenRevocationStore:
    def __init__(self, client: Redis) -> None:
        self._client = client

    async def close(self) -> None:
        await self._client.aclose()

    async def revoke(self, jti: str, ttl_seconds: int) -> None:
        await self._client.set(_KEY_PREFIX + jti, "1", ex=ttl_seconds)

    async def is_revoked(self, jti: str) -> bool:
        return bool(await self._client.exists(_KEY_PREFIX + jti))


class NullTokenRevocationStore:
    """Fallback used when Redis is not configured.

    Tokens then stay valid until they expire; logout and refresh rotation cannot
    revoke them. The compose stack always provides ``REDIS_URL``.
    """

    async def revoke(self, jti: str, ttl_seconds: int) -> None:
        return None

    async def is_revoked(self, jti: str) -> bool:
        return False

    async def close(self) -> None:
        return None
