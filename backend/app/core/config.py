"""Application settings, loaded from environment variables (12-factor style).

Every secret comes from the environment; nothing sensitive is hard-coded.
`get_settings()` is cached so settings are parsed once per process.
"""

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: Literal["local", "test", "staging", "production"] = "local"
    log_level: str = "INFO"

    database_url: str = "postgresql+asyncpg://screeniq:screeniq@localhost:5432/screeniq"
    redis_url: str = "redis://localhost:6379/0"

    jwt_secret: str = "change-me"  # noqa: S105 - overridden via env in every real deploy
    jwt_access_ttl_min: int = 15
    jwt_refresh_ttl_days: int = 7

    s3_endpoint: str = "http://localhost:9000"
    s3_bucket: str = "screeniq-resumes"
    s3_access_key: str = "minioadmin"
    s3_secret_key: str = "minioadmin"  # noqa: S105

    gemini_api_key: str = ""
    llm_model: str = "gemini-2.5-flash"
    embedding_model: str = ""

    # Comma-separated in the env var, parsed into a list here.
    cors_origins_raw: str = Field(default="http://localhost:3000", alias="CORS_ORIGINS")

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.cors_origins_raw.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
