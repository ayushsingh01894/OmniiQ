from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings, loaded from environment variables (and optional .env)."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "OmniIQ"
    environment: str = Field(default="development", pattern="^(development|test|production)$")
    log_level: str = "INFO"
    api_v1_prefix: str = "/api/v1"
    cors_origins: list[str] = ["http://localhost:5173"]

    # No defaults on purpose: the app must be told where its database is and given a signing key.
    database_url: str = Field(min_length=1)
    secret_key: str = Field(min_length=32)

    access_token_expire_minutes: int = Field(default=30, ge=1, le=1440)

    # In-memory, per-process limits (see docs/security.md for the limitation).
    login_rate_limit_attempts: int = Field(default=10, ge=1)
    login_rate_limit_window_seconds: int = Field(default=60, ge=1)
    register_rate_limit_attempts: int = Field(default=5, ge=1)
    register_rate_limit_window_seconds: int = Field(default=3600, ge=1)
    # Per user: uploads and cleaning/profile requests are expensive.
    job_rate_limit_attempts: int = Field(default=30, ge=1)
    job_rate_limit_window_seconds: int = Field(default=60, ge=1)

    # --- file storage and upload limits ---
    storage_root: str = "./storage"
    max_upload_bytes: int = Field(default=25 * 1024 * 1024, ge=1024)
    max_dataset_rows: int = Field(default=500_000, ge=1)
    max_dataset_columns: int = Field(default=500, ge=1)
    max_xlsx_uncompressed_bytes: int = Field(default=200 * 1024 * 1024, ge=1024)

    # --- background jobs ---
    # "inline": run in the API process after the response (dev/tests, no Redis needed).
    # "celery": send to a Celery worker through Redis (what docker-compose uses).
    job_backend: Literal["inline", "celery"] = "inline"
    redis_url: str = "redis://localhost:6379/0"
    job_time_limit_seconds: int = Field(default=300, ge=10)


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
