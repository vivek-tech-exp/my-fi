"""Top-level API router."""

from fastapi import APIRouter

from app.api.routes.imports import router as imports_router
from app.api.routes.system import router as system_router
from app.api.routes.transactions import router as transactions_router
from app.api.routes.ui import router as ui_router

api_router = APIRouter()
api_router.include_router(system_router)
api_router.include_router(imports_router)
api_router.include_router(transactions_router)
api_router.include_router(ui_router)
