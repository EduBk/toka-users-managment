"""Role microservice entry point."""

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI

from api.errors import register_role_exception_handlers
from api.router import router
from app_common.app import create_service_app
from app_common.config import BaseServiceSettings
from app_common.event_publisher import RabbitMqEventPublisher
from app_common.jwt_auth import JwtValidator
from infrastructure.messaging.outbox_worker import OutboxWorker
from infrastructure.persistence.database import (
    create_database_engine,
    create_session_factory,
)
from infrastructure.persistence.outbox_store import SqlAlchemyOutbox
from infrastructure.persistence.unit_of_work import SqlAlchemyUnitOfWork


class Settings(BaseServiceSettings):
    service_name: str = "role-service"
    database_url: str
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
    app.state.jwt_validator = JwtValidator(
        issuer=settings.jwt_issuer,
        audience=settings.jwt_audience,
        jwks_url=settings.jwks_url,
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
        await engine.dispose()


app = create_service_app(settings, routers=[router])
app.router.lifespan_context = lifespan
register_role_exception_handlers(app)
