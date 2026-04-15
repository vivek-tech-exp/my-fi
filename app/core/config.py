"""Typed application settings."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="MY_FI_",
        extra="ignore",
    )

    project_name: str = "my-fi"
    app_version: str = "0.1.0"
    environment: Literal["local", "development", "test", "production"] = "local"
    api_host: str = "127.0.0.1"
    api_port: int = 8000
    data_dir: Path = Field(default=PROJECT_ROOT / "data")
    uploads_dir: Path = Field(default=PROJECT_ROOT / "data" / "uploads")
    quarantine_dir: Path = Field(default=PROJECT_ROOT / "data" / "quarantine")
    storage_dir: Path = Field(default=PROJECT_ROOT / "storage")
    test_fixtures_dir: Path = Field(default=PROJECT_ROOT / "tests" / "fixtures")

    @property
    def required_directories(self) -> tuple[Path, ...]:
        return (
            self.data_dir,
            self.uploads_dir,
            self.quarantine_dir,
            self.storage_dir,
            self.test_fixtures_dir,
        )


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings."""

    return Settings()
