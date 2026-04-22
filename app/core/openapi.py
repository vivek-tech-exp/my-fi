"""OpenAPI schema compatibility helpers."""

from __future__ import annotations

from collections.abc import MutableMapping
from typing import Any, cast

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi


def install_openapi_schema(application: FastAPI) -> None:
    """Install the app OpenAPI schema with Swagger-compatible file fields."""

    def custom_openapi() -> dict[str, Any]:
        if application.openapi_schema:
            return cast(dict[str, Any], application.openapi_schema)

        openapi_schema = get_openapi(
            title=application.title,
            version=application.version,
            summary=application.summary,
            description=application.description,
            routes=application.routes,
        )
        _rewrite_binary_file_schemas(openapi_schema)
        application.openapi_schema = openapi_schema
        return cast(dict[str, Any], application.openapi_schema)

    cast(Any, application).openapi = custom_openapi


def _rewrite_binary_file_schemas(value: object) -> None:
    """Rewrite OpenAPI 3.1 file fields into the format Swagger UI renders well."""

    if isinstance(value, MutableMapping):
        if value.get("contentMediaType") == "application/octet-stream":
            value.pop("contentMediaType", None)
            value["format"] = "binary"

        for nested_value in value.values():
            _rewrite_binary_file_schemas(nested_value)
        return

    if isinstance(value, list):
        for nested_value in value:
            _rewrite_binary_file_schemas(nested_value)
