"""
Application Configuration Module.

Uses pydantic-settings to manage environment variables safely.
Reads from .env file when present; does not hard-code sensitive credentials.
"""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    ENVIRONMENT: str = "development"
    LOG_LEVEL: str = "INFO"

    # Async database connection string
    DATABASE_URL: str = Field(
        default="postgresql+asyncpg://city_anpr_user:city_anpr_secure_password@localhost:5432/city_anpr",
        description="Async database connection string for SQLAlchemy + asyncpg",
    )

    @property
    def sync_database_url(self) -> str:
        """Return synchronous connection URL (for tools or Alembic sync runner)."""
        url = self.DATABASE_URL
        if url.startswith("postgresql+asyncpg://"):
            return url.replace("postgresql+asyncpg://", "postgresql://", 1)
        return url


settings = Settings()
