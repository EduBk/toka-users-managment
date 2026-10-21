"""Redis implementation of :class:`UserCache`.

Listings are versioned: writes bump ``users:list:version`` instead of scanning
and deleting every cached page. Old entries become unreachable and expire with
the TTL. Any Redis failure degrades to PostgreSQL reads.
"""

import json
import logging
from datetime import datetime
from typing import Any
from uuid import UUID

from redis.asyncio import Redis
from redis.exceptions import RedisError

from application.dto import UserPage
from app_common.logging import log_event
from domain.user.entity import User
from domain.user.exceptions import UserDomainError
from domain.user.value_objects import Email, Profile, UserName, UserStatus

logger = logging.getLogger(__name__)

_DETAIL_KEY = "users:user:{user_id}"
_LIST_VERSION_KEY = "users:list:version"
_LIST_KEY = "users:list:v{version}:{page}:{page_size}"


class RedisUserCache:
    def __init__(self, client: Redis, ttl_seconds: int) -> None:
        self._client = client
        self._ttl_seconds = ttl_seconds

    async def get_user(self, user_id: UUID) -> User | None:
        key = _DETAIL_KEY.format(user_id=user_id)
        raw = await self._read(key)
        if raw is None:
            return None
        try:
            return _deserialize_user(json.loads(raw))
        except (ValueError, KeyError, TypeError, UserDomainError) as exc:
            _log_error("get_user", key, exc)
            return None

    async def set_user(self, user: User) -> None:
        key = _DETAIL_KEY.format(user_id=user.id)
        await self._write(key, json.dumps(_serialize_user(user)))

    async def get_page(self, *, page: int, page_size: int) -> UserPage | None:
        version = await self._list_version()
        key = _LIST_KEY.format(
            version=version, page=page, page_size=page_size
        )
        raw = await self._read(key)
        if raw is None:
            return None
        try:
            payload = json.loads(raw)
            return UserPage(
                items=[_deserialize_user(item) for item in payload["items"]],
                total=int(payload["total"]),
                page=int(payload["page"]),
                page_size=int(payload["page_size"]),
            )
        except (ValueError, KeyError, TypeError, UserDomainError) as exc:
            _log_error("get_page", key, exc)
            return None

    async def set_page(self, page: UserPage) -> None:
        version = await self._list_version()
        key = _LIST_KEY.format(
            version=version, page=page.page, page_size=page.page_size
        )
        payload = {
            "items": [_serialize_user(user) for user in page.items],
            "total": page.total,
            "page": page.page,
            "page_size": page.page_size,
        }
        await self._write(key, json.dumps(payload))

    async def invalidate(self, user_id: UUID) -> None:
        key = _DETAIL_KEY.format(user_id=user_id)
        try:
            await self._client.delete(key)
            await self._client.incr(_LIST_VERSION_KEY)
        except RedisError as exc:
            _log_error("invalidate", key, exc)

    async def _read(self, key: str) -> str | None:
        try:
            raw = await self._client.get(key)
        except RedisError as exc:
            _log_error("read", key, exc)
            return None
        if raw is None:
            log_event(logger, logging.INFO, "cache_miss", key=key)
        else:
            log_event(logger, logging.INFO, "cache_hit", key=key)
        return raw

    async def _write(self, key: str, value: str) -> None:
        try:
            await self._client.set(key, value, ex=self._ttl_seconds)
        except RedisError as exc:
            _log_error("write", key, exc)

    async def _list_version(self) -> int:
        try:
            current = await self._client.get(_LIST_VERSION_KEY)
        except RedisError as exc:
            _log_error("list_version", _LIST_VERSION_KEY, exc)
            return 0
        return int(current) if current is not None else 0


class NullUserCache:
    """Fallback used when Redis is not configured: reads always miss."""

    async def get_user(self, user_id: UUID) -> User | None:
        return None

    async def set_user(self, user: User) -> None:
        return None

    async def get_page(self, *, page: int, page_size: int) -> UserPage | None:
        return None

    async def set_page(self, page: UserPage) -> None:
        return None

    async def invalidate(self, user_id: UUID) -> None:
        return None


def _log_error(operation: str, key: str, exc: Exception) -> None:
    log_event(
        logger,
        logging.ERROR,
        "cache_error",
        operation=operation,
        key=key,
        error=str(exc),
    )


def _serialize_user(user: User) -> dict[str, Any]:
    return {
        "id": str(user.id),
        "email": user.email.value,
        "name": user.name.value,
        "status": user.status.value,
        "profile": user.profile.value,
        "created_at": user.created_at.isoformat(),
        "updated_at": user.updated_at.isoformat(),
    }


def _deserialize_user(payload: dict[str, Any]) -> User:
    return User(
        id=UUID(payload["id"]),
        email=Email(payload["email"]),
        name=UserName(payload["name"]),
        status=UserStatus.parse(payload["status"]),
        profile=Profile(payload["profile"]),
        created_at=datetime.fromisoformat(payload["created_at"]),
        updated_at=datetime.fromisoformat(payload["updated_at"]),
    )
