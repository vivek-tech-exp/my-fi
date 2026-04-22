"""Models for import upload flows."""

from datetime import UTC, date, datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.parsing import RawRowAuditSummary
from app.models.validation import ValidationReportRecord


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


class PreParseNormalizationResult(BaseModel):
    """Normalized text and metadata derived from the raw uploaded file."""

    normalized_text: str | None = None
    encoding_detected: str | None = None
    delimiter_detected: str | None = None
    quarantine_required: bool = False
    failure_reason: str | None = None


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
    parser_name: str
    status: ImportStatus
    statement_start_date: date | None = None
    statement_end_date: date | None = None
    encoding_detected: str | None = None
    delimiter_detected: str | None = None
    header_detected: bool = False
    raw_rows_recorded: int = Field(default=0, ge=0)
    suspicious_rows_recorded: int = Field(default=0, ge=0)
    transactions_imported: int = Field(default=0, ge=0)
    duplicate_transactions_detected: int = Field(default=0, ge=0)
    exact_duplicate_transactions: int = Field(default=0, ge=0)
    probable_duplicate_transactions: int = Field(default=0, ge=0)
    ambiguous_transactions_detected: int = Field(default=0, ge=0)
    uploaded_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    message: str

    @classmethod
    def from_source_file_record(
        cls,
        record: SourceFileRecord,
        *,
        parser_name: str,
        audit_summary: RawRowAuditSummary | None = None,
        transactions_imported: int = 0,
        duplicate_transactions_detected: int = 0,
        exact_duplicate_transactions: int = 0,
        probable_duplicate_transactions: int = 0,
        ambiguous_transactions_detected: int = 0,
        duplicate_file: bool = False,
        message: str,
    ) -> "UploadCsvResponse":
        raw_row_summary = audit_summary or RawRowAuditSummary()
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
            parser_name=parser_name,
            status=record.import_status,
            statement_start_date=record.statement_start_date,
            statement_end_date=record.statement_end_date,
            encoding_detected=record.encoding_detected,
            delimiter_detected=record.delimiter_detected,
            header_detected=raw_row_summary.header_detected,
            raw_rows_recorded=raw_row_summary.raw_rows_recorded,
            suspicious_rows_recorded=raw_row_summary.suspicious_rows_recorded,
            transactions_imported=transactions_imported,
            duplicate_transactions_detected=duplicate_transactions_detected,
            exact_duplicate_transactions=exact_duplicate_transactions,
            probable_duplicate_transactions=probable_duplicate_transactions,
            ambiguous_transactions_detected=ambiguous_transactions_detected,
            uploaded_at=record.uploaded_at,
            message=message,
        )


class UploadCsvBatchItemResponse(BaseModel):
    """Per-file result for a batch CSV upload."""

    original_filename: str
    status_code: int
    result: UploadCsvResponse | None = None
    error: str | None = None


class UploadCsvBatchResponse(BaseModel):
    """Structured response for a multi-file CSV upload."""

    total_files: int = Field(ge=0)
    succeeded: int = Field(ge=0)
    failed: int = Field(ge=0)
    duplicates: int = Field(ge=0)
    results: list[UploadCsvBatchItemResponse] = Field(default_factory=list)


class ImportSummaryResponse(BaseModel):
    """Summary metadata for an import."""

    file_id: UUID
    bank_name: BankName
    account_id: str | None = None
    original_filename: str
    file_hash: str
    status: ImportStatus
    uploaded_at: datetime
    parser_version: str
    statement_start_date: date | None = None
    statement_end_date: date | None = None

    @classmethod
    def from_source_file_record(cls, record: SourceFileRecord) -> "ImportSummaryResponse":
        return cls(
            file_id=record.file_id,
            bank_name=record.bank_name,
            account_id=record.account_id,
            original_filename=record.original_filename,
            file_hash=record.file_hash,
            status=record.import_status,
            uploaded_at=record.uploaded_at,
            parser_version=record.parser_version,
            statement_start_date=record.statement_start_date,
            statement_end_date=record.statement_end_date,
        )


class ImportDetailResponse(ImportSummaryResponse):
    """Detailed import metadata."""

    stored_path: str
    file_size_bytes: int
    encoding_detected: str | None = None
    delimiter_detected: str | None = None
    report: ValidationReportRecord | None = None

    @classmethod
    def from_source_file_record(
        cls,
        record: SourceFileRecord,
        *,
        report: ValidationReportRecord | None = None,
    ) -> "ImportDetailResponse":
        return cls(
            file_id=record.file_id,
            bank_name=record.bank_name,
            account_id=record.account_id,
            original_filename=record.original_filename,
            file_hash=record.file_hash,
            status=record.import_status,
            uploaded_at=record.uploaded_at,
            parser_version=record.parser_version,
            statement_start_date=record.statement_start_date,
            statement_end_date=record.statement_end_date,
            stored_path=record.stored_path,
            file_size_bytes=record.file_size_bytes,
            encoding_detected=record.encoding_detected,
            delimiter_detected=record.delimiter_detected,
            report=report,
        )
