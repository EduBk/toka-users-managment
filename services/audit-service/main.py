"""Audit microservice entry point."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import Field

from api.router import router
from app_common.app import create_service_app
from app_common.config import BaseServiceSettings
from app_common.event_consumer import (
    IdempotentEventHandler,
    RabbitMqEventConsumer,
)
from app_common.event_publisher import RabbitMqEventPublisher
from app_common.jwt_auth import JwtValidator
from application.use_cases.record_audit_entry import RecordAuditEntry
from infrastructure.messaging.consumer import AuditEventHandler
from infrastructure.persistence.mongo_repository import (
    MongoAuditEntryRepository,
    MongoProcessedEventStore,
)

QUEUE_NAME = "audit-service"


class Settings(BaseServiceSettings):
    service_name: str = "audit-service"
    mongo_uri: str
    mongo_database: str
    rabbitmq_url: str
    jwks_url: str
    jwt_issuer: str = "auth-service"
    jwt_audience: str = "user-management"
    audit_retention_days: int = Field(default=90, ge=1)


settings = Settings()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    mongo_client = AsyncIOMotorClient(settings.mongo_uri, tz_aware=True)
    repository = MongoAuditEntryRepository(
        mongo_client[settings.mongo_database],
        retention_days=settings.audit_retention_days,
    )
    publisher = RabbitMqEventPublisher(settings.rabbitmq_url)
    consumer: RabbitMqEventConsumer | None = None

    try:
        await repository.ensure_indexes()
        handler = IdempotentEventHandler(
            AuditEventHandler(RecordAuditEntry(repository)),
            MongoProcessedEventStore(repository),
        )
        consumer = RabbitMqEventConsumer(
            settings.rabbitmq_url,
            QUEUE_NAME,
            handler,
            publisher,
        )
        await consumer.start()

        app.state.audit_repository = repository
        app.state.jwt_validator = JwtValidator(
            issuer=settings.jwt_issuer,
            audience=settings.jwt_audience,
            jwks_url=settings.jwks_url,
        )
        yield
    finally:
        if consumer is not None:
            await consumer.stop()
        await publisher.close()
        mongo_client.close()


app = create_service_app(settings, routers=[router])
app.router.lifespan_context = lifespan
