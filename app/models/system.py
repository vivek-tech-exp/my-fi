"""Models for system endpoints."""

from typing import Literal

from pydantic import BaseModel


class ServiceInfoResponse(BaseModel):
    """Public metadata for the running service."""

    service_name: str
    environment: str
    version: str
    docs_url: str
    health_url: str


class HealthResponse(BaseModel):
    """Health check payload."""

    status: Literal["ok"]
    environment: str
    version: str
