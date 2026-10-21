"""Template microservice.

Copy this folder to create a new service. It only wires the shared app factory
and the Clean Architecture layers; business code starts in ``domain/``.
"""

from api.router import router
from app_common.app import create_service_app
from app_common.config import BaseServiceSettings


class Settings(BaseServiceSettings):
    service_name: str = "template-service"


settings = Settings()
app = create_service_app(settings, routers=[router])
