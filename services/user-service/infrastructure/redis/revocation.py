"""Redis-backed check of revoked access tokens (E2.4, wired in E2.6)."""

import logging

from redis.asyncio import Redis
from redis.exceptions import RedisError

from app_common.logging import log_event

logger = logging.getLogger(__name__)

_KEY_PREFIX = "auth:revoked:"


class RedisTokenRevocationChecker:
    """Reads ``auth:revoked:{jti}`` as written by ``auth-service``.

    If Redis is unavailable the check fails open: the signature and expiry are
    still validated and short-lived access tokens bound the exposure.
    """

    def __init__(self, client: Redis) -> None:
        self._client = client

    async def is_revoked(self, jti: str) -> bool:
        try:
            return bool(await self._client.exists(_KEY_PREFIX + jti))
        except RedisError as exc:
            log_event(
                logger,
                logging.ERROR,
                "revocation_check_failed",
                jti=jti,
                error=str(exc),
            )
            return False
