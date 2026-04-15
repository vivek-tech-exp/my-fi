"""Smoke tests for the bootstrap service routes."""

from fastapi.testclient import TestClient


def test_service_info_endpoint(client: TestClient) -> None:
    response = client.get("/")

    assert response.status_code == 200
    assert response.json() == {
        "service_name": "my-fi",
        "environment": "local",
        "version": "0.1.0",
        "docs_url": "/docs",
        "health_url": "/health",
    }


def test_health_endpoint(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "environment": "local",
        "version": "0.1.0",
    }


def test_docs_endpoint_is_available(client: TestClient) -> None:
    response = client.get("/docs")

    assert response.status_code == 200
    assert "swagger-ui" in response.text.lower()
