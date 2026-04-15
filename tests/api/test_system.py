"""Smoke tests for the bootstrap service routes."""

from app.core.config import get_settings
from fastapi.testclient import TestClient


def test_service_info_endpoint(client: TestClient) -> None:
    settings = get_settings()
    response = client.get("/")

    assert response.status_code == 200
    assert response.json() == {
        "service_name": "my-fi",
        "environment": settings.environment,
        "version": settings.app_version,
        "docs_url": "/docs",
        "health_url": "/health",
    }


def test_health_endpoint(client: TestClient) -> None:
    settings = get_settings()
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "environment": settings.environment,
        "version": settings.app_version,
    }


def test_docs_endpoint_is_available(client: TestClient) -> None:
    response = client.get("/docs")

    assert response.status_code == 200
    assert "swagger-ui" in response.text.lower()
