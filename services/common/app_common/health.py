"""Liveness probe shared by every service.

Services that depend on external stores add their own ``/ready`` endpoint with
the dependency checks they need.
"""

from fastapi import APIRouter
from pydantic import BaseModel

from app_common.config import BaseServiceSettings


class HealthResponse(BaseModel):
    status: str = "ok"
    service: str
    version: str
    environment: str


def build_health_router(settings: BaseServiceSettings) -> APIRouter:
    router = APIRouter(tags=["health"])

    @router.get("/health", response_model=HealthResponse, summary="Liveness probe")
    def health() -> HealthResponse:
        return HealthResponse(
            service=settings.service_name,
            version=settings.service_version,
            environment=settings.environment,
        )

    return router
