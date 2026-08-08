import logging
import os
from datetime import datetime
from functools import lru_cache
from typing import Annotated, Any

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    """Runtime configuration loaded lazily from environment and `.env`."""

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore", case_sensitive=True
    )

    DATABASE_URL: str = ""
    DB_POOL_SIZE: int = 20
    DB_MAX_OVERFLOW: int = 10
    DB_POOL_PRE_PING: bool = True
    DB_POOL_RECYCLE_SECONDS: int = 3600
    DB_CONNECT_TIMEOUT: int = 10
    DB_KEEPALIVES: int = 1
    DB_KEEPALIVES_IDLE: int = 30
    DB_KEEPALIVES_INTERVAL: int = 5
    DB_KEEPALIVES_COUNT: int = 5

    SECRET_KEY: str = ""
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    ACTIVATION_TOKEN_EXPIRE_MINUTES: int = 60
    PASSWORD_RESET_TOKEN_EXPIRE_MINUTES: int = 15
    PASSWORD_RESET_COOLDOWN_MINUTES: int = 15
    ACTIVATION_EMAIL_COOLDOWN_MINUTES: int = 120
    LOGIN_MAX_FAILED_ATTEMPTS: int = 5
    LOGIN_LOCKOUT_MINUTES: int = 15

    UPLOAD_DIR: str = "uploads"
    MAX_FILE_SIZE_MB: int = 5
    CHUNK_SIZE_BYTES: int = 1024 * 1024

    POSTMARK_KEY: str = ""
    POSTMARK_URL: str = "https://api.postmarkapp.com/email"
    EMAIL_FROM: str = "do-not-reply@hackthevalley.io"
    BULK_MAX_CONCURRENT: int = 10
    BULK_CHUNK_SIZE: int = 100
    BULK_WARN_THRESHOLD: int = 1000

    CORS_ORIGINS: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["*"]
    )
    ENABLE_API_DOCS: bool = True
    FRONTEND_URL: str = "https://hackthevalley.io"
    BACKEND_URL: str = "http://localhost:8000"
    EVENT_NAME: str = "Hack the Valley 11"
    EVENT_START_DATE: datetime = datetime.fromisoformat("2026-10-16T00:00:00-04:00")
    EVENT_END_DATE: datetime = datetime.fromisoformat("2026-10-18T23:59:59-04:00")
    EVENT_LOCATION: str = "IA building, UofT Scarborough"
    APPLICATION_START_DATE: datetime = datetime.fromisoformat(
        "2026-06-01T00:00:00-04:00"
    )
    APPLICATION_END_DATE: datetime = datetime.fromisoformat(
        "2026-09-01T00:00:00-04:00"
    )
    RSVP_DUE_DATE: str = "October 9th 2026"
    APPLE_TEAM_IDENTIFIER: str | None = None
    APPLE_PASS_TYPE_IDENTIFIER: str | None = None
    APPLE_WALLET_KEY_PASSWORD: str | None = None
    GOOGLE_WALLET_ISSUER_ID: str | None = None
    GOOGLE_WALLET_CLASS_ID: str | None = None
    GOOGLE_WALLET_PASS_URL: str | None = None

    @property
    def MAX_FILE_SIZE_BYTES(self) -> int:
        return self.MAX_FILE_SIZE_MB * 1024 * 1024

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_origins(cls, value: Any) -> Any:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value


@lru_cache
def get_settings() -> Settings:
    deprecated = sorted(name for name in os.environ if name.startswith("BULK_EMAIL_"))
    if deprecated:
        logger.warning(
            "Unused deprecated environment variables: %s; use BULK_MAX_CONCURRENT, "
            "BULK_CHUNK_SIZE, and BULK_WARN_THRESHOLD",
            ", ".join(deprecated),
        )
    return Settings()


class _SettingsProxyMeta(type):
    def __getattr__(cls, name: str) -> Any:
        return getattr(get_settings(), cls._aliases.get(name, name))


class DatabaseConfig(metaclass=_SettingsProxyMeta):
    _aliases = {
        "URL": "DATABASE_URL",
        "POOL_SIZE": "DB_POOL_SIZE",
        "MAX_OVERFLOW": "DB_MAX_OVERFLOW",
        "POOL_PRE_PING": "DB_POOL_PRE_PING",
        "POOL_RECYCLE_SECONDS": "DB_POOL_RECYCLE_SECONDS",
        "CONNECT_TIMEOUT": "DB_CONNECT_TIMEOUT",
        "KEEPALIVES": "DB_KEEPALIVES",
        "KEEPALIVES_IDLE": "DB_KEEPALIVES_IDLE",
        "KEEPALIVES_INTERVAL": "DB_KEEPALIVES_INTERVAL",
        "KEEPALIVES_COUNT": "DB_KEEPALIVES_COUNT",
    }

    @classmethod
    def validate(cls) -> None:
        if not cls.URL:
            raise ValueError("DATABASE_URL environment variable is not set")


class SecurityConfig(metaclass=_SettingsProxyMeta):
    _aliases: dict[str, str] = {}

    @classmethod
    def validate(cls) -> None:
        if not cls.SECRET_KEY:
            raise ValueError("SECRET_KEY environment variable is not set")


class FileUploadConfig(metaclass=_SettingsProxyMeta):
    _aliases: dict[str, str] = {}


class EmailConfig(metaclass=_SettingsProxyMeta):
    _aliases = {"POSTMARK_API_KEY": "POSTMARK_KEY", "FROM_EMAIL": "EMAIL_FROM"}

    @classmethod
    def validate(cls) -> None:
        if not cls.POSTMARK_API_KEY:
            raise ValueError("POSTMARK_KEY environment variable is not set")


class AppConfig(metaclass=_SettingsProxyMeta):
    _aliases: dict[str, str] = {}

    @staticmethod
    def get_activation_url(token: str) -> str:
        return f"{AppConfig.FRONTEND_URL}/activate?token={token}"

    @staticmethod
    def get_password_reset_url(token: str) -> str:
        return f"{AppConfig.FRONTEND_URL}/reset-password?token={token}"

    @staticmethod
    def get_apple_wallet_url(application_id: str) -> str:
        return f"{AppConfig.BACKEND_URL}/api/account/apple-wallet/{application_id}"

    @staticmethod
    def get_event_date_range() -> str:
        return (
            f"{AppConfig.EVENT_START_DATE.strftime('%b %d')} - "
            f"{AppConfig.EVENT_END_DATE.strftime('%d, %Y')}"
        )


def validate_config() -> None:
    DatabaseConfig.validate()
    SecurityConfig.validate()
    EmailConfig.validate()
