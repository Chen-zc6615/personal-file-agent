from pathlib import Path
from typing import Any
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    """Application configuration loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="ASSISTANT_",
        extra="ignore"
    )

    app_name: str

    model_name: str
    temperature: float = Field(ge=0, le=2)
    max_tokens: int = Field(ge=1)

    sqlite_path: Path

    mcp_servers: dict[str, dict[str, Any]] = Field(
        default_factory=dict
    )

settings = Settings()