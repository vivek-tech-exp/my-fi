"""Services for source-file intake and local storage."""

from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from re import sub
from uuid import uuid4

from app.core.config import get_settings
from app.db.source_files import get_source_file_by_hash, insert_source_file
from app.models.imports import BankName, ImportStatus, SourceFileRecord, UploadCsvResponse


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
    existing_record = get_source_file_by_hash(file_hash)
    if existing_record is not None:
        return UploadCsvResponse.from_source_file_record(
            existing_record,
            duplicate_file=True,
            message="Matching file already registered. Returning existing import metadata.",
        )

    file_id = uuid4()
    sanitized_filename = _sanitize_filename(original_filename)
    destination_dir = settings.uploads_dir / bank_name.value / file_hash[:2]
    destination_dir.mkdir(parents=True, exist_ok=True)
    stored_path = destination_dir / f"{file_hash}__{sanitized_filename}"
    stored_path.write_bytes(file_bytes)

    source_file = SourceFileRecord(
        file_id=file_id,
        original_filename=original_filename,
        stored_path=str(stored_path),
        bank_name=bank_name,
        account_id=account_id,
        file_hash=file_hash,
        file_size_bytes=len(file_bytes),
        uploaded_at=datetime.now(UTC),
        parser_version=settings.default_parser_version,
        import_status=ImportStatus.RECEIVED,
    )

    try:
        persisted_record = insert_source_file(source_file)
    except Exception:
        existing_record = get_source_file_by_hash(file_hash)
        if existing_record is not None:
            if stored_path != Path(existing_record.stored_path):
                stored_path.unlink(missing_ok=True)

            return UploadCsvResponse.from_source_file_record(
                existing_record,
                duplicate_file=True,
                message="Matching file already registered. Returning existing import metadata.",
            )

        stored_path.unlink(missing_ok=True)
        raise

    return UploadCsvResponse.from_source_file_record(
        persisted_record,
        duplicate_file=False,
        message=(
            "File stored locally and registered for processing. Parsing and "
            "validation will be added in subsequent milestones."
        ),
    )


def _sanitize_filename(filename: str) -> str:
    """Return a filesystem-safe filename while preserving readability."""

    raw_name = Path(filename).name.strip()
    if not raw_name:
        return "upload.csv"

    cleaned_name = sub(r"[^A-Za-z0-9._-]+", "_", raw_name)
    return cleaned_name.strip("._") or "upload.csv"
