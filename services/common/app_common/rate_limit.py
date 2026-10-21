"""Fixed-window rate limiting shared by the services (E2.11).

Counters live in Redis so every replica shares them. If Redis fails the request
is allowed (fail-open, like the cache) and ``rate_limit_unavailable`` is logged.
"""

import logging
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Protocol

from fastapi import Request
from redis.asyncio import Redis
from redis.exceptions import RedisError

from app_common.errors import TooManyRequestsError
from app_common.logging import log_event

logger = logging.getLogger("app_common.rate_limit")

_KEY_PREFIX = "ratelimit:"


@dataclass(frozen=True, slots=True)
class RateLimitRule:
    limit: int
    window_seconds: int

    def __post_init__(self) -> None:
        if self.limit < 1:
            raise ValueError("limit must be >= 1")
        if self.window_seconds < 1:
            raise ValueError("window_seconds must be >= 1")


@dataclass(frozen=True, slots=True)
class RateLimitDecision:
    allowed: bool
    retry_after_seconds: int


class RateLimiter(Protocol):
    async def hit(self, key: str, rule: RateLimitRule) -> RateLimitDecision: ...


def _window(rule: RateLimitRule, now: float) -> tuple[int, int]:
    window = int(now) // rule.window_seconds
    retry_after = rule.window_seconds - int(now) % rule.window_seconds
    return window, retry_after


class RedisRateLimiter:
    def __init__(
        self, client: Redis, *, clock: Callable[[], float] = time.time
    ) -> None:
        self._client = client
        self._clock = clock

    async def hit(self, key: str, rule: RateLimitRule) -> RateLimitDecision:
        window, retry_after = _window(rule, self._clock())
        redis_key = f"{_KEY_PREFIX}{key}:{window}"
        try:
            async with self._client.pipeline(transaction=True) as pipe:
                pipe.incr(redis_key)
                pipe.expire(redis_key, rule.window_seconds, nx=True)
                count, _ = await pipe.execute()
        except RedisError as exc:
            log_event(
                logger,
                logging.WARNING,
                "rate_limit_unavailable",
                error=type(exc).__name__,
            )
            return RateLimitDecision(allowed=True, retry_after_seconds=0)
        return RateLimitDecision(
            allowed=int(count) <= rule.limit, retry_after_seconds=retry_after
        )


class InMemoryRateLimiter:
    """Per-process limiter for tests and for services running without Redis."""

    def __init__(self, *, clock: Callable[[], float] = time.time) -> None:
        self._clock = clock
        self._counts: dict[tuple[str, int], int] = {}

    async def hit(self, key: str, rule: RateLimitRule) -> RateLimitDecision:
        window, retry_after = _window(rule, self._clock())
        self._counts = {
            entry: count
            for entry, count in self._counts.items()
            if entry[1] >= window
        }
        count = self._counts.get((key, window), 0) + 1
        self._counts[(key, window)] = count
        return RateLimitDecision(
            allowed=count <= rule.limit, retry_after_seconds=retry_after
        )


class RateLimitPolicy:
    """Applies one rule with one limiter; exposed through ``app.state.rate_limit``."""

    def __init__(self, limiter: RateLimiter, rule: RateLimitRule) -> None:
        self._limiter = limiter
        self._rule = rule

    async def enforce(self, scope: str, subject: str) -> None:
        decision = await self._limiter.hit(f"{scope}:{subject}", self._rule)
        if decision.allowed:
            return
        log_event(logger, logging.WARNING, "rate_limit_exceeded", scope=scope)
        raise TooManyRequestsError(
            "too many requests, retry later",
            details={"retry_after_seconds": decision.retry_after_seconds},
            headers={"Retry-After": str(decision.retry_after_seconds)},
        )


def client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def limit_by_client_ip(scope: str) -> Callable[[Request], Awaitable[None]]:
    """Dependency factory for unauthenticated endpoints (login, register...)."""

    async def dependency(request: Request) -> None:
        policy: RateLimitPolicy | None = getattr(
            request.app.state, "rate_limit", None
        )
        if policy is not None:
            await policy.enforce(scope, client_ip(request))

    return dependency
