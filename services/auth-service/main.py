"""Auth microservice entry point."""

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI
from pydantic import Field

from api.errors import register_auth_exception_handlers
from api.jwks import router as jwks_router
from api.router import router
from app_common.app import create_service_app
from app_common.config import BaseServiceSettings
from app_common.event_publisher import RabbitMqEventPublisher
from app_common.jwt_auth import JwtValidator
from app_common.rate_limit import (
    InMemoryRateLimiter,
    RateLimitPolicy,
    RateLimitRule,
    RedisRateLimiter,
)
from infrastructure.messaging.outbox_worker import OutboxWorker
from infrastructure.persistence.database import (
    create_database_engine,
    create_session_factory,
)
from infrastructure.persistence.outbox_store import SqlAlchemyOutbox
from infrastructure.redis.client import create_redis_client
from infrastructure.redis.revocation_store import (
    NullTokenRevocationStore,
    RedisTokenRevocationStore,
)
from infrastructure.role_service.client import (
    HttpUserAccessProvider,
    NullUserAccessProvider,
)
from infrastructure.security.bcrypt_hasher import BcryptPasswordHasher
from infrastructure.security.jwks import build_jwks
from infrastructure.security.keys import read_key_pair
from infrastructure.security.rs256_token_service import Rs256TokenService

ROLE_SERVICE_SCOPE = "roles:read"
SERVICE_TOKEN_TTL_SECONDS = 60


class Settings(BaseServiceSettings):
    service_name: str = "auth-service"
    database_url: str
    redis_url: str = ""
    rabbitmq_url: str = ""
    jwt_private_key_path: str
    jwt_public_key_path: str
    jwt_issuer: str = "auth-service"
    jwt_audience: str = "user-management"
    access_token_ttl_seconds: int = 900
    refresh_token_ttl_days: int = 7
    role_service_url: str = ""
    role_service_timeout_seconds: float = 2.0
    auth_rate_limit_requests: int = Field(default=10, ge=1)
    auth_rate_limit_window_seconds: int = Field(default=60, ge=1)


settings = Settings()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    engine = create_database_engine(settings.database_url)
    session_factory = create_session_factory(engine)
    app.state.session_factory = session_factory
    app.state.password_hasher = BcryptPasswordHasher()
    outbox = SqlAlchemyOutbox(session_factory, producer=settings.service_name)
    app.state.event_outbox = outbox

    publisher: RabbitMqEventPublisher | None = None
    worker_task: asyncio.Task[None] | None = None
    stop_worker: asyncio.Event | None = None

    private_key_pem, public_key_pem = read_key_pair(
        settings.jwt_private_key_path, settings.jwt_public_key_path
    )
    redis_client = (
        create_redis_client(settings.redis_url) if settings.redis_url else None
    )
    revocations = (
        RedisTokenRevocationStore(redis_client)
        if redis_client is not None
        else NullTokenRevocationStore()
    )

    app.state.revocation_store = revocations
    app.state.rate_limit = RateLimitPolicy(
        RedisRateLimiter(redis_client)
        if redis_client is not None
        else InMemoryRateLimiter(),
        RateLimitRule(
            limit=settings.auth_rate_limit_requests,
            window_seconds=settings.auth_rate_limit_window_seconds,
        ),
    )
    app.state.token_service = Rs256TokenService(
        private_key_pem=private_key_pem,
        public_key_pem=public_key_pem,
        issuer=settings.jwt_issuer,
        audience=settings.jwt_audience,
        access_token_ttl_seconds=settings.access_token_ttl_seconds,
        refresh_token_ttl_days=settings.refresh_token_ttl_days,
    )
    app.state.jwt_validator = JwtValidator(
        issuer=settings.jwt_issuer,
        audience=settings.jwt_audience,
        public_key=public_key_pem,
        revocation=revocations,
    )
    app.state.jwks = build_jwks(public_key_pem)
    token_service = app.state.token_service
    user_access = (
        HttpUserAccessProvider(
            settings.role_service_url,
            service_token=lambda: token_service.issue_service_token(
                subject=settings.service_name,
                scopes=(ROLE_SERVICE_SCOPE,),
                ttl_seconds=SERVICE_TOKEN_TTL_SECONDS,
            ).token,
            timeout_seconds=settings.role_service_timeout_seconds,
        )
        if settings.role_service_url
        else NullUserAccessProvider()
    )
    app.state.user_access_provider = user_access

    if settings.rabbitmq_url:
        publisher = RabbitMqEventPublisher(settings.rabbitmq_url)
        stop_worker = asyncio.Event()
        worker_task = asyncio.create_task(
            OutboxWorker(outbox, publisher).run(stop_worker),
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
        await engine.dispose()
        await revocations.close()
        await user_access.close()


app = create_service_app(settings, routers=[router, jwks_router])
app.router.lifespan_context = lifespan
register_auth_exception_handlers(app)
