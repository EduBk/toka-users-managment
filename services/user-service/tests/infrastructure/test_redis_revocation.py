"""Tests for the distributed revoked-token check."""

from infrastructure.redis.revocation import RedisTokenRevocationChecker
from tests.infrastructure.fakes import FailingRedis, FakeRedis


async def test_reports_only_tokens_present_in_redis() -> None:
    redis = FakeRedis()
    redis.data["auth:revoked:jti-1"] = "1"
    checker = RedisTokenRevocationChecker(redis)

    assert await checker.is_revoked("jti-1") is True
    assert await checker.is_revoked("jti-2") is False


async def test_fails_open_when_redis_is_unavailable() -> None:
    checker = RedisTokenRevocationChecker(FailingRedis())

    assert await checker.is_revoked("jti-1") is False
