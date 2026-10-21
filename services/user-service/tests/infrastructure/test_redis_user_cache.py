"""Tests for the Redis read cache and its degradation behaviour."""

from application.dto import UserPage
from domain.user.entity import User
from domain.user.value_objects import Email, UserName
from infrastructure.cache.redis_cache import NullUserCache, RedisUserCache
from tests.infrastructure.fakes import FailingRedis, FakeRedis


def _user(email: str = "ana@example.com") -> User:
    user = User.create(email=Email(email), name=UserName("Ana Perez"))
    user.pull_events()
    return user


async def test_get_user_returns_none_on_a_miss() -> None:
    cache = RedisUserCache(FakeRedis(), ttl_seconds=30)

    assert await cache.get_user(_user().id) is None


async def test_user_round_trip_uses_the_configured_ttl() -> None:
    redis = FakeRedis()
    cache = RedisUserCache(redis, ttl_seconds=30)
    user = _user()

    await cache.set_user(user)
    cached = await cache.get_user(user.id)

    assert cached is not None
    assert cached.id == user.id
    assert cached.email == user.email
    assert cached.name == user.name
    assert cached.status == user.status
    assert cached.profile == user.profile
    assert cached.created_at == user.created_at
    assert cached.updated_at == user.updated_at
    assert redis.ttls[f"users:user:{user.id}"] == 30


async def test_page_round_trip() -> None:
    cache = RedisUserCache(FakeRedis(), ttl_seconds=30)
    users = [_user(), _user("luis@example.com")]
    page = UserPage(items=users, total=2, page=1, page_size=20)

    await cache.set_page(page)
    cached = await cache.get_page(page=1, page_size=20)

    assert cached is not None
    assert cached.total == 2
    assert cached.page == 1
    assert cached.page_size == 20
    assert [user.id for user in cached.items] == [user.id for user in users]


async def test_invalidate_drops_the_detail_and_every_cached_page() -> None:
    redis = FakeRedis()
    cache = RedisUserCache(redis, ttl_seconds=30)
    user = _user()
    page = UserPage(items=[user], total=1, page=1, page_size=20)
    await cache.set_user(user)
    await cache.set_page(page)

    await cache.invalidate(user.id)

    assert await cache.get_user(user.id) is None
    assert await cache.get_page(page=1, page_size=20) is None
    assert redis.data["users:list:version"] == "1"


async def test_redis_failures_degrade_to_a_miss_without_raising() -> None:
    cache = RedisUserCache(FailingRedis(), ttl_seconds=30)
    user = _user()

    assert await cache.get_user(user.id) is None
    assert await cache.get_page(page=1, page_size=20) is None
    await cache.set_user(user)
    await cache.set_page(UserPage(items=[user], total=1, page=1, page_size=20))
    await cache.invalidate(user.id)


async def test_null_cache_always_misses() -> None:
    cache = NullUserCache()
    user = _user()

    await cache.set_user(user)
    await cache.set_page(UserPage(items=[user], total=1, page=1, page_size=20))

    assert await cache.get_user(user.id) is None
    assert await cache.get_page(page=1, page_size=20) is None
    await cache.invalidate(user.id)
