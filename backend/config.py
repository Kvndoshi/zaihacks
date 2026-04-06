"""Friction server configuration — loads from environment / .env file."""

from __future__ import annotations

import os

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Detect Vercel serverless environment
_IS_VERCEL = bool(os.environ.get("VERCEL"))
_DEFAULT_DB = "/tmp/friction.db" if _IS_VERCEL else "db/friction.db"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    ZAI_API_KEY: str = Field(default="", description="Z.ai API key for GLM 5.1")
    LLM_MODEL: str = Field(default="glm-5.1", description="GLM model name")
    DB_PATH: str = Field(default=_DEFAULT_DB, description="SQLite database path")
    CORS_ORIGINS: list[str] = Field(
        default=["*"],
        description="Allowed CORS origins",
    )
    MAX_DELIBERATION_TURNS: int = Field(
        default=20,
        description="Maximum number of deliberation turns before auto-complete",
    )
    SERVER_HOST: str = Field(default="0.0.0.0", description="Server bind host")
    SERVER_PORT: int = Field(default=8080, description="Server bind port")


config = Settings()  # type: ignore[call-arg]
