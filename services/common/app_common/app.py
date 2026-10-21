"""FastAPI application factory shared by every service."""

from collections.abc import Sequence

from fastapi import APIRouter, FastAPI

from app_common.config import BaseServiceSettings
from app_common.errors import register_exception_handlers
from app_common.health import build_health_router
from app_common.logging import configure_logging
from app_common.middleware import TraceIdMiddleware


def create_service_app(
    settings: BaseServiceSettings,
    *,
    routers: Sequence[APIRouter] = (),
    title: str | None = None,
    description: str | None = None,
) -> FastAPI:
    configure_logging(settings)

    expose_docs = settings.environment != "production"
    app = FastAPI(
        title=title or settings.service_name,
        version=settings.service_version,
        description=description,
        docs_url="/docs" if expose_docs else None,
        redoc_url="/redoc" if expose_docs else None,
        openapi_url="/openapi.json" if expose_docs else None,
    )
    app.add_middleware(TraceIdMiddleware)
    register_exception_handlers(app)
    app.include_router(build_health_router(settings))
    for router in routers:
        app.include_router(router)
    return app
