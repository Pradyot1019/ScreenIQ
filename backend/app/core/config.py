"""Application settings, loaded from environment variables (12-factor style).

Every secret comes from the environment; nothing sensitive is hard-coded.
`get_settings()` is cached so settings are parsed once per process.
"""

from functools import lru_cache
from typing import Literal
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: Literal["local", "test", "staging", "production"] = "local"
    log_level: str = "INFO"

    database_url: str = "postgresql+asyncpg://screeniq:screeniq@localhost:5432/screeniq"
    redis_url: str = "redis://localhost:6379/0"

    # Dev-only default (32+ chars so HS256 has a full-length key). Refused outside local/test.
    jwt_secret: str = "change-me-dev-only-not-a-real-secret-000"  # noqa: S105
    jwt_access_ttl_min: int = 15
    jwt_refresh_ttl_days: int = 7

    s3_endpoint: str = "http://localhost:9000"
    s3_public_endpoint: str = ""  # what browsers use for signed URLs; empty = s3_endpoint
    s3_region: str = "us-east-1"  # Cloudflare R2 uses "auto"
    s3_bucket: str = "screeniq-resumes"
    s3_access_key: str = "minioadmin"
    s3_secret_key: str = "minioadmin"  # noqa: S105

    gemini_api_key: str = ""
    llm_model: str = "gemini-3.5-flash-lite"  # free tier; see ADR 0003
    llm_timeout_s: float = 60.0  # spec NFR: LLM call timeout of 60 s
    embedding_model: str = ""

    # Comma-separated in the env var, parsed into a list here.
    cors_origins_raw: str = Field(default="http://localhost:3000", alias="CORS_ORIGINS")

    @field_validator("database_url")
    @classmethod
    def _asyncpg_url(cls, url: str) -> str:
        """Accept the URL hosts hand out (e.g. Neon's `postgresql://...?sslmode=require`)
        and turn it into what SQLAlchemy + asyncpg expect."""
        parts = urlsplit(url)
        scheme = {"postgres": "postgresql+asyncpg", "postgresql": "postgresql+asyncpg"}.get(
            parts.scheme, parts.scheme
        )
        query = dict(parse_qsl(parts.query))
        if "sslmode" in query:  # libpq spelling -> asyncpg spelling
            query["ssl"] = query.pop("sslmode")
        query.pop("channel_binding", None)  # libpq-only option asyncpg rejects
        return urlunsplit(parts._replace(scheme=scheme, query=urlencode(query)))

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.cors_origins_raw.split(",") if o.strip()]

    @property
    def cookie_secure(self) -> bool:
        # Browsers only send Secure cookies over HTTPS; local dev runs on plain HTTP.
        return self.app_env in ("staging", "production")

    @model_validator(mode="after")
    def _no_default_secret_in_prod(self) -> "Settings":
        # Anyone who knows the JWT secret can mint tokens for any user.
        if self.app_env in ("staging", "production") and (
            "change-me" in self.jwt_secret or len(self.jwt_secret) < 32
        ):
            raise ValueError("JWT_SECRET must be set to a random value of 32+ characters")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
