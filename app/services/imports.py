"""Services for source-file intake and local storage."""

from hashlib import sha256
from pathlib import Path
from re import sub
from uuid import uuid4

from app.core.config import get_settings
from app.models.imports import BankName, ImportStatus, UploadCsvResponse


def store_uploaded_csv(
    *,
    file_bytes: bytes,
    original_filename: str,
    bank_name: BankName,
    account_id: str | None,
) -> UploadCsvResponse:
    """Persist an uploaded CSV file and return its initial import metadata."""

    settings = get_settings()
    file_hash = sha256(file_bytes).hexdigest()
    sanitized_filename = _sanitize_filename(original_filename)
    destination_dir = settings.uploads_dir / bank_name.value / file_hash[:2]
    destination_dir.mkdir(parents=True, exist_ok=True)
    stored_path = destination_dir / f"{file_hash}__{sanitized_filename}"
    stored_path.write_bytes(file_bytes)

    return UploadCsvResponse(
        file_id=uuid4(),
        file_hash=file_hash,
        bank_name=bank_name,
        account_id=account_id,
        original_filename=original_filename,
        stored_path=str(stored_path),
        file_size_bytes=len(file_bytes),
        status=ImportStatus.RECEIVED,
        message=(
            "File stored locally. Import registry, idempotency, and parsing "
            "will be added in subsequent milestones."
        ),
    )


def _sanitize_filename(filename: str) -> str:
    """Return a filesystem-safe filename while preserving readability."""

    raw_name = Path(filename).name.strip()
    if not raw_name:
        return "upload.csv"

    cleaned_name = sub(r"[^A-Za-z0-9._-]+", "_", raw_name)
    return cleaned_name.strip("._") or "upload.csv"
