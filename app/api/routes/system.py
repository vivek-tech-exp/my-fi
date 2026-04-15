"""System routes for service discovery and health checks."""

from fastapi import APIRouter

from app.core.config import get_settings
from app.models.system import HealthResponse, ServiceInfoResponse

router = APIRouter(tags=["system"])


@router.get("/", response_model=ServiceInfoResponse, summary="Get service metadata")
def read_service_info() -> ServiceInfoResponse:
    settings = get_settings()
    return ServiceInfoResponse(
        service_name=settings.project_name,
        environment=settings.environment,
        version=settings.app_version,
        docs_url="/docs",
        health_url="/health",
    )


@router.get("/health", response_model=HealthResponse, summary="Check service health")
def read_health() -> HealthResponse:
    settings = get_settings()
    return HealthResponse(
        status="ok",
        environment=settings.environment,
        version=settings.app_version,
    )
