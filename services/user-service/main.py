"""User microservice entry point."""

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI

from api.errors import register_user_exception_handlers
from api.router import router
from app_common.app import create_service_app
from app_common.config import BaseServiceSettings
from app_common.event_publisher import RabbitMqEventPublisher
from app_common.jwt_auth import JwtValidator
from infrastructure.cache.redis_cache import NullUserCache, RedisUserCache
from infrastructure.messaging.outbox_worker import OutboxWorker
from infrastructure.persistence.database import (
    create_database_engine,
    create_session_factory,
)
from infrastructure.persistence.outbox_store import SqlAlchemyOutbox
from infrastructure.persistence.unit_of_work import SqlAlchemyUnitOfWork
from infrastructure.redis.client import create_redis_client
from infrastructure.redis.revocation import RedisTokenRevocationChecker


class Settings(BaseServiceSettings):
    service_name: str = "user-service"
    database_url: str
    redis_url: str = ""
    cache_ttl_seconds: int = 60
    rabbitmq_url: str = ""
    jwks_url: str
    jwt_issuer: str = "auth-service"
    jwt_audience: str = "user-management"


settings = Settings()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    engine = create_database_engine(settings.database_url)
    session_factory = create_session_factory(engine)
    app.state.unit_of_work_factory = lambda: SqlAlchemyUnitOfWork(
        session_factory, producer=settings.service_name
    )

    redis_client = (
        create_redis_client(settings.redis_url) if settings.redis_url else None
    )
    app.state.user_cache = (
        RedisUserCache(redis_client, settings.cache_ttl_seconds)
        if redis_client is not None
        else NullUserCache()
    )
    app.state.jwt_validator = JwtValidator(
        issuer=settings.jwt_issuer,
        audience=settings.jwt_audience,
        jwks_url=settings.jwks_url,
        revocation=(
            RedisTokenRevocationChecker(redis_client)
            if redis_client is not None
            else None
        ),
    )

    publisher: RabbitMqEventPublisher | None = None
    worker_task: asyncio.Task[None] | None = None
    stop_worker: asyncio.Event | None = None

    if settings.rabbitmq_url:
        publisher = RabbitMqEventPublisher(settings.rabbitmq_url)
        stop_worker = asyncio.Event()
        worker_task = asyncio.create_task(
            OutboxWorker(
                SqlAlchemyOutbox(session_factory), publisher
            ).run(stop_worker),
            name="outbox-worker",
        )

    try:
        yield
    finally:
        if stop_worker is not None:
            stop_worker.set()
        if worker_task is not None:
            with suppress(asyncio.CancelledError):
                await worker_task
        if publisher is not None:
            await publisher.close()
        if redis_client is not None:
            await redis_client.aclose()
        await engine.dispose()


app = create_service_app(settings, routers=[router])
app.router.lifespan_context = lifespan
register_user_exception_handlers(app)
