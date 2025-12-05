"""
Application configuration management.

Environment variables should be defined in a .env file or set in the deployment environment.
"""

import os
from datetime import datetime
from typing import Optional

from dotenv import load_dotenv

load_dotenv()


class DatabaseConfig:
    """Database connection configuration."""

    URL: str = os.getenv("DATABASE_URL", "")
    POOL_SIZE: int = int(os.getenv("DB_POOL_SIZE", "20"))
    MAX_OVERFLOW: int = int(os.getenv("DB_MAX_OVERFLOW", "10"))
    POOL_PRE_PING: bool = os.getenv("DB_POOL_PRE_PING", "true").lower() == "true"
    POOL_RECYCLE_SECONDS: int = int(os.getenv("DB_POOL_RECYCLE_SECONDS", "3600"))
    CONNECT_TIMEOUT: int = int(os.getenv("DB_CONNECT_TIMEOUT", "10"))
    KEEPALIVES: int = int(os.getenv("DB_KEEPALIVES", "1"))
    KEEPALIVES_IDLE: int = int(os.getenv("DB_KEEPALIVES_IDLE", "30"))
    KEEPALIVES_INTERVAL: int = int(os.getenv("DB_KEEPALIVES_INTERVAL", "5"))
    KEEPALIVES_COUNT: int = int(os.getenv("DB_KEEPALIVES_COUNT", "5"))

    @classmethod
    def validate(cls):
        """Validate required database configuration."""
        if not cls.URL:
            raise ValueError(
                "DATABASE_URL environment variable is not set. "
                "Please configure the database connection string."
            )


class SecurityConfig:
    """Security and authentication configuration."""

    SECRET_KEY: str = os.getenv("SECRET_KEY", "")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(
        os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60")
    )
    ACTIVATION_TOKEN_EXPIRE_MINUTES: int = int(
        os.getenv("ACTIVATION_TOKEN_EXPIRE_MINUTES", "60")
    )
    PASSWORD_RESET_TOKEN_EXPIRE_MINUTES: int = int(
        os.getenv("PASSWORD_RESET_TOKEN_EXPIRE_MINUTES", "15")
    )
    PASSWORD_RESET_COOLDOWN_MINUTES: int = int(
        os.getenv("PASSWORD_RESET_COOLDOWN_MINUTES", "15")
    )
    ACTIVATION_EMAIL_COOLDOWN_MINUTES: int = int(
        os.getenv("ACTIVATION_EMAIL_COOLDOWN_MINUTES", "120")
    )

    @classmethod
    def validate(cls):
        """Validate required security configuration."""
        if not cls.SECRET_KEY:
            raise ValueError(
                "SECRET_KEY environment variable is not set. "
                "Please set a strong secret key for JWT token signing."
            )


class FileUploadConfig:
    """File upload configuration."""

    UPLOAD_DIR: str = os.getenv("UPLOAD_DIR", "uploads")
    MAX_FILE_SIZE_BYTES: int = int(os.getenv("MAX_FILE_SIZE_MB", "5")) * 1024 * 1024
    CHUNK_SIZE_BYTES: int = 1024 * 1024


class EmailConfig:
    """Email service configuration."""

    POSTMARK_API_KEY: str = os.getenv("POSTMARK_KEY", "")
    POSTMARK_URL: str = "https://api.postmarkapp.com/email"
    FROM_EMAIL: str = os.getenv("EMAIL_FROM", "do-not-reply@hackthevalley.io")

    BULK_MAX_CONCURRENT: int = int(os.getenv("BULK_EMAIL_MAX_CONCURRENT", "10"))
    BULK_CHUNK_SIZE: int = int(os.getenv("BULK_EMAIL_CHUNK_SIZE", "100"))
    BULK_WARN_THRESHOLD: int = int(os.getenv("BULK_EMAIL_WARN_THRESHOLD", "1000"))

    @classmethod
    def validate(cls):
        """Validate required email configuration."""
        if not cls.POSTMARK_API_KEY:
            raise ValueError(
                "POSTMARK_KEY environment variable is not set. "
                "Email functionality will not work."
            )


class AppConfig:
    """Application-specific configuration."""

    FRONTEND_URL: str = os.getenv("FRONTEND_URL", "https://hackthevalley.io")
    BACKEND_URL: str = os.getenv("BACKEND_URL", "https://api.hackthevalley.io")

    EVENT_NAME: str = os.getenv("EVENT_NAME", "Hack the Valley X")
    EVENT_START_DATE: datetime = datetime.fromisoformat(
        os.getenv("EVENT_START_DATE", "2025-10-03T00:00:00-04:00")
    )
    EVENT_END_DATE: datetime = datetime.fromisoformat(
        os.getenv("EVENT_END_DATE", "2025-10-05T23:59:59-04:00")
    )
    EVENT_LOCATION: str = os.getenv("EVENT_LOCATION", "IA building, UofT Scarborough")

    APPLICATION_START_DATE: datetime = datetime.fromisoformat(
        os.getenv("APPLICATION_START_DATE", "2025-06-01T00:00:00-04:00")
    )
    APPLICATION_END_DATE: datetime = datetime.fromisoformat(
        os.getenv("APPLICATION_END_DATE", "2025-09-01T00:00:00-04:00")
    )
    RSVP_DUE_DATE: str = os.getenv("RSVP_DUE_DATE", "September 26th 2025")

    APPLE_TEAM_IDENTIFIER: Optional[str] = os.getenv("APPLE_TEAM_IDENTIFIER")
    APPLE_PASS_TYPE_IDENTIFIER: Optional[str] = os.getenv("APPLE_PASS_TYPE_IDENTIFIER")
    APPLE_WALLET_KEY_PASSWORD: Optional[str] = os.getenv("APPLE_WALLET_KEY_PASSWORD")
    GOOGLE_WALLET_ISSUER_ID: Optional[str] = os.getenv("GOOGLE_WALLET_ISSUER_ID")
    GOOGLE_WALLET_CLASS_ID: Optional[str] = os.getenv("GOOGLE_WALLET_CLASS_ID")

    @staticmethod
    def get_activation_url(token: str) -> str:
        """Generate account activation URL."""
        return f"{AppConfig.FRONTEND_URL}/account-activate?token={token}"

    @staticmethod
    def get_password_reset_url(token: str) -> str:
        """Generate password reset URL."""
        return f"{AppConfig.FRONTEND_URL}/reset-password?token={token}"

    @staticmethod
    def get_apple_wallet_url(application_id: str) -> str:
        """Generate Apple Wallet pass URL."""
        return f"{AppConfig.BACKEND_URL}/api/account/apple-wallet/{application_id}"

    @staticmethod
    def get_event_date_range() -> str:
        """Get formatted event date range."""
        start = AppConfig.EVENT_START_DATE.strftime("%b %d")
        end = AppConfig.EVENT_END_DATE.strftime("%d, %Y")
        return f"{start} - {end}"


def validate_config():
    """Validate all required configuration on startup."""
    DatabaseConfig.validate()
    SecurityConfig.validate()
    EmailConfig.validate()
