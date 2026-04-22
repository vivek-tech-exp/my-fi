"""Shared test fixtures."""

from collections.abc import Iterator
from pathlib import Path

import pytest
from app.core.config import Settings, get_settings
from app.main import app
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def configure_test_environment(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Iterator[None]:
    runtime_root = tmp_path / "runtime"
    monkeypatch.setenv("MY_FI_ENVIRONMENT", "test")
    monkeypatch.setenv("MY_FI_DATA_DIR", str(runtime_root / "data"))
    monkeypatch.setenv("MY_FI_UPLOADS_DIR", str(runtime_root / "data" / "uploads"))
    monkeypatch.setenv("MY_FI_QUARANTINE_DIR", str(runtime_root / "data" / "quarantine"))
    monkeypatch.setenv("MY_FI_STORAGE_DIR", str(runtime_root / "storage"))
    monkeypatch.setenv("MY_FI_LOGS_DIR", str(runtime_root / "storage" / "logs"))
    monkeypatch.setenv(
        "MY_FI_UPLOAD_STAGING_DIR",
        str(runtime_root / "storage" / "upload-staging"),
    )
    monkeypatch.setenv("MY_FI_DATABASE_PATH", str(runtime_root / "storage" / "my_fi.duckdb"))
    monkeypatch.setenv("MY_FI_TEST_FIXTURES_DIR", str(runtime_root / "tests" / "fixtures"))
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def settings() -> Settings:
    return get_settings()


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client
