"""Routes for the lightweight local UI shell."""

from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse

WEB_STATIC_DIR = Path(__file__).resolve().parents[2] / "web" / "static"

router = APIRouter(tags=["ui"])


@router.get("/ui", include_in_schema=False)
def get_ui() -> FileResponse:
    """Serve the local UI shell."""

    return FileResponse(WEB_STATIC_DIR / "index.html")
