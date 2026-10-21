from typing import Any

import pytest
from fastapi import APIRouter, Depends
from fastapi.testclient import TestClient
from redis.exceptions import ConnectionError

from app_common.app import create_service_app
from app_common.config import BaseServiceSettings
from app_common.errors import TooManyRequestsError
from app_common.rate_limit import (
    InMemoryRateLimiter,
    RateLimitPolicy,
    RateLimitRule,
    RedisRateLimiter,
    limit_by_client_ip,
)


class _Clock:
    def __init__(self, now: float) -> None:
        self.now = now

    def __call__(self) -> float:
        return self.now


class _FakePipeline:
    def __init__(self, redis: "_FakeRedis") -> None:
        self._redis = redis
        self._ops: list[tuple[str, tuple[Any, ...]]] = []

    async def __aenter__(self) -> "_FakePipeline":
        return self

    async def __aexit__(self, *_exc_info: object) -> None:
        return None

    def incr(self, key: str) -> None:
        self._ops.append(("incr", (key,)))

    def expire(self, key: str, seconds: int, *, nx: bool = False) -> None:
        self._ops.append(("expire", (key, seconds, nx)))

    async def execute(self) -> list[Any]:
        if self._redis.failing:
            raise ConnectionError("connection refused")
        results: list[Any] = []
        for name, args in self._ops:
            if name == "incr":
                self._redis.counts[args[0]] = self._redis.counts.get(args[0], 0) + 1
                results.append(self._redis.counts[args[0]])
            else:
                self._redis.expirations.setdefault(args[0], args[1])
                results.append(True)
        return results


class _FakeRedis:
    def __init__(self, *, failing: bool = False) -> None:
        self.failing = failing
        self.counts: dict[str, int] = {}
        self.expirations: dict[str, int] = {}

    def pipeline(self, *, transaction: bool) -> _FakePipeline:
        return _FakePipeline(self)


RULE = RateLimitRule(limit=2, window_seconds=60)


@pytest.mark.parametrize("limit, window", [(0, 60), (5, 0)])
def test_rule_rejects_non_positive_values(limit: int, window: int) -> None:
    with pytest.raises(ValueError):
        RateLimitRule(limit=limit, window_seconds=window)


async def test_in_memory_limiter_blocks_after_the_limit_and_resets() -> None:
    clock = _Clock(1_000)
    limiter = InMemoryRateLimiter(clock=clock)

    decisions = [await limiter.hit("login:1.2.3.4", RULE) for _ in range(3)]
    other_key = await limiter.hit("login:5.6.7.8", RULE)
    clock.now += 60
    next_window = await limiter.hit("login:1.2.3.4", RULE)

    assert [decision.allowed for decision in decisions] == [True, True, False]
    assert decisions[2].retry_after_seconds == 20
    assert other_key.allowed is True
    assert next_window.allowed is True


async def test_redis_limiter_counts_per_window_with_expiry() -> None:
    redis = _FakeRedis()
    limiter = RedisRateLimiter(redis, clock=_Clock(1_000))  # type: ignore[arg-type]

    decisions = [await limiter.hit("login:1.2.3.4", RULE) for _ in range(3)]

    assert [decision.allowed for decision in decisions] == [True, True, False]
    assert redis.counts == {"ratelimit:login:1.2.3.4:16": 3}
    assert redis.expirations == {"ratelimit:login:1.2.3.4:16": 60}


async def test_redis_limiter_fails_open() -> None:
    limiter = RedisRateLimiter(_FakeRedis(failing=True))  # type: ignore[arg-type]

    decision = await limiter.hit("login:1.2.3.4", RULE)

    assert decision.allowed is True


async def test_policy_raises_429_with_retry_after() -> None:
    policy = RateLimitPolicy(
        InMemoryRateLimiter(clock=_Clock(1_000)),
        RateLimitRule(limit=1, window_seconds=60),
    )
    await policy.enforce("auth:login", "1.2.3.4")

    with pytest.raises(TooManyRequestsError) as error:
        await policy.enforce("auth:login", "1.2.3.4")

    assert error.value.status_code == 429
    assert error.value.headers == {"Retry-After": "20"}


def test_dependency_limits_by_client_ip_and_is_optional() -> None:
    router = APIRouter()

    @router.post("/login", dependencies=[Depends(limit_by_client_ip("auth:login"))])
    async def login() -> dict[str, bool]:
        return {"ok": True}

    app = create_service_app(
        BaseServiceSettings(service_name="test-service"), routers=[router]
    )
    client = TestClient(app)

    assert client.post("/login").status_code == 200

    app.state.rate_limit = RateLimitPolicy(
        InMemoryRateLimiter(), RateLimitRule(limit=1, window_seconds=60)
    )
    first = client.post("/login")
    second = client.post("/login")

    assert first.status_code == 200
    assert second.status_code == 429
    assert second.json()["code"] == "rate_limited"
    assert int(second.headers["Retry-After"]) >= 1
