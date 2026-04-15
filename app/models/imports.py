"""Models for import upload flows."""

from datetime import UTC, date, datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, Field


class BankName(StrEnum):
    """Supported banks for V1 ingestion."""

    HDFC = "hdfc"
    KOTAK = "kotak"
    FEDERAL = "federal"


class ImportStatus(StrEnum):
    """Upload and processing lifecycle states."""

    RECEIVED = "RECEIVED"
    PROCESSING = "PROCESSING"
    PASS = "PASS"
    PASS_WITH_WARNINGS = "PASS_WITH_WARNINGS"
    FAIL_NEEDS_REVIEW = "FAIL_NEEDS_REVIEW"


class SourceFileRecord(BaseModel):
    """Persisted metadata for an uploaded source file."""

    file_id: UUID
    original_filename: str
    stored_path: str
    bank_name: BankName
    account_id: str | None = None
    file_hash: str = Field(min_length=64, max_length=64)
    file_size_bytes: int = Field(ge=1)
    uploaded_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    parser_version: str
    import_status: ImportStatus
    statement_start_date: date | None = None
    statement_end_date: date | None = None
    encoding_detected: str | None = None
    delimiter_detected: str | None = None


class UploadCsvResponse(BaseModel):
    """Structured response for a stored CSV upload."""

    file_id: UUID
    file_hash: str = Field(min_length=64, max_length=64)
    duplicate_file: bool = False
    bank_name: BankName
    account_id: str | None = None
    original_filename: str
    stored_path: str
    file_size_bytes: int = Field(ge=1)
    parser_version: str
    status: ImportStatus
    uploaded_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    message: str

    @classmethod
    def from_source_file_record(
        cls,
        record: SourceFileRecord,
        *,
        duplicate_file: bool = False,
        message: str,
    ) -> "UploadCsvResponse":
        return cls(
            file_id=record.file_id,
            file_hash=record.file_hash,
            duplicate_file=duplicate_file,
            bank_name=record.bank_name,
            account_id=record.account_id,
            original_filename=record.original_filename,
            stored_path=record.stored_path,
            file_size_bytes=record.file_size_bytes,
            parser_version=record.parser_version,
            status=record.import_status,
            uploaded_at=record.uploaded_at,
            message=message,
        )
