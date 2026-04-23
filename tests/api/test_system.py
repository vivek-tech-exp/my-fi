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


def test_local_ui_shell_is_available(client: TestClient) -> None:
    response = client.get("/ui")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert 'href="/ui/assets/styles.css"' in response.text
    assert 'src="/ui/assets/main.js"' in response.text


def test_local_ui_static_assets_are_available(client: TestClient) -> None:
    css_response = client.get("/ui/assets/styles.css")
    js_response = client.get("/ui/assets/main.js")

    assert css_response.status_code == 200
    assert "text/css" in css_response.headers["content-type"]
    assert ".app-shell" in css_response.text
    assert js_response.status_code == 200
    assert "javascript" in js_response.headers["content-type"]
    assert "uploadCsvBatch" in js_response.text


def test_local_ui_routes_are_not_added_to_openapi(client: TestClient) -> None:
    response = client.get("/openapi.json")

    assert response.status_code == 200
    assert "/ui" not in response.json()["paths"]
    assert "/ui/assets/styles.css" not in response.json()["paths"]


def test_openapi_renders_upload_fields_as_swagger_file_inputs(client: TestClient) -> None:
    response = client.get("/openapi.json")
    cached_response = client.get("/openapi.json")

    assert response.status_code == 200
    assert cached_response.status_code == 200
    schemas = response.json()["components"]["schemas"]
    single_upload_schema = schemas["Body_upload_csv_imports_csv_post"]["properties"]["file"]
    batch_upload_schema = schemas["Body_upload_csv_batch_imports_csv_batch_post"]["properties"][
        "files"
    ]

    assert single_upload_schema == {
        "type": "string",
        "format": "binary",
        "title": "File",
        "description": "CSV file to ingest",
    }
    assert batch_upload_schema["items"] == {"type": "string", "format": "binary"}
    assert batch_upload_schema["type"] == "array"
