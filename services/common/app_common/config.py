"""Environment-based settings shared by every service."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class BaseServiceSettings(BaseSettings):
    """Common settings.

    Each service subclasses this class and adds its own fields (database URLs,
    broker URLs, ...). Values come from environment variables or from a local
    ``.env`` file; secrets are never hardcoded.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    service_name: str
    service_version: str = "0.1.0"
    environment: str = "local"
    log_level: str = "INFO"
