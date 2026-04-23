"""Models for import upload flows."""

from datetime import UTC, date, datetime
from enum import StrEnum
from typing import TypedDict
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.parsing import RawRowAuditSummary
from app.models.validation import ValidationReportRecord


class _ImportSummaryFields(TypedDict):
    total_rows: int
    accepted_rows: int
    ignored_rows: int
    suspicious_rows: int
    duplicate_rows: int
    transactions_imported: int
    issue_count: int
    error_count: int
    warning_count: int
    info_count: int
    has_errors: bool
    has_warnings: bool
    has_suspicious_rows: bool
    has_duplicates: bool
    needs_action: bool


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
    """Action-oriented import summary for UI filtering and review."""

    file_id: UUID
    bank_name: BankName
    account_id: str | None = None
    original_filename: str
    file_hash: str
    status: ImportStatus
    trust_status: str
    uploaded_at: datetime
    parser_version: str
    statement_start_date: date | None = None
    statement_end_date: date | None = None
    total_rows: int = Field(default=0, ge=0)
    accepted_rows: int = Field(default=0, ge=0)
    ignored_rows: int = Field(default=0, ge=0)
    suspicious_rows: int = Field(default=0, ge=0)
    duplicate_rows: int = Field(default=0, ge=0)
    transactions_imported: int = Field(default=0, ge=0)
    issue_count: int = Field(default=0, ge=0)
    error_count: int = Field(default=0, ge=0)
    warning_count: int = Field(default=0, ge=0)
    info_count: int = Field(default=0, ge=0)
    has_errors: bool = False
    has_warnings: bool = False
    has_suspicious_rows: bool = False
    has_duplicates: bool = False
    needs_action: bool = False
    recommended_action: str

    @classmethod
    def from_source_file_record(
        cls,
        record: SourceFileRecord,
        *,
        report: ValidationReportRecord | None = None,
    ) -> "ImportSummaryResponse":
        summary = _summary_fields(record, report)
        return cls(
            file_id=record.file_id,
            bank_name=record.bank_name,
            account_id=record.account_id,
            original_filename=record.original_filename,
            file_hash=record.file_hash,
            status=record.import_status,
            trust_status=_trust_status(record.import_status),
            uploaded_at=record.uploaded_at,
            parser_version=record.parser_version,
            statement_start_date=record.statement_start_date,
            statement_end_date=record.statement_end_date,
            **summary,
            recommended_action=_recommended_action(record.import_status, report),
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
        summary = _summary_fields(record, report)
        return cls(
            file_id=record.file_id,
            bank_name=record.bank_name,
            account_id=record.account_id,
            original_filename=record.original_filename,
            file_hash=record.file_hash,
            status=record.import_status,
            trust_status=_trust_status(record.import_status),
            uploaded_at=record.uploaded_at,
            parser_version=record.parser_version,
            statement_start_date=record.statement_start_date,
            statement_end_date=record.statement_end_date,
            **summary,
            recommended_action=_recommended_action(record.import_status, report),
            stored_path=record.stored_path,
            file_size_bytes=record.file_size_bytes,
            encoding_detected=record.encoding_detected,
            delimiter_detected=record.delimiter_detected,
            report=report,
        )


def _summary_fields(
    record: SourceFileRecord,
    report: ValidationReportRecord | None,
) -> _ImportSummaryFields:
    error_count = sum(1 for issue in report.issues if issue.severity == "error") if report else 0
    warning_count = (
        sum(1 for issue in report.issues if issue.severity == "warning") if report else 0
    )
    info_count = sum(1 for issue in report.issues if issue.severity == "info") if report else 0
    has_errors = record.import_status == ImportStatus.FAIL_NEEDS_REVIEW or error_count > 0
    has_warnings = record.import_status == ImportStatus.PASS_WITH_WARNINGS or warning_count > 0
    suspicious_rows = report.suspicious_rows if report else 0
    duplicate_rows = report.duplicate_rows if report else 0
    return {
        "total_rows": report.total_rows if report else 0,
        "accepted_rows": report.accepted_rows if report else 0,
        "ignored_rows": report.ignored_rows if report else 0,
        "suspicious_rows": suspicious_rows,
        "duplicate_rows": duplicate_rows,
        "transactions_imported": report.transactions_imported if report else 0,
        "issue_count": len(report.issues) if report else 0,
        "error_count": error_count,
        "warning_count": warning_count,
        "info_count": info_count,
        "has_errors": has_errors,
        "has_warnings": has_warnings,
        "has_suspicious_rows": suspicious_rows > 0,
        "has_duplicates": duplicate_rows > 0,
        "needs_action": has_errors or has_warnings or suspicious_rows > 0,
    }


def _trust_status(status: ImportStatus) -> str:
    if status == ImportStatus.PASS:
        return "ready"
    if status == ImportStatus.PASS_WITH_WARNINGS:
        return "review_warnings"
    if status == ImportStatus.FAIL_NEEDS_REVIEW:
        return "needs_review"
    return status.value.lower()


def _recommended_action(
    status: ImportStatus,
    report: ValidationReportRecord | None,
) -> str:
    if status == ImportStatus.FAIL_NEEDS_REVIEW:
        return "Review validation issues and diagnostics before trusting this import."
    if status == ImportStatus.PASS_WITH_WARNINGS:
        return "Review warnings, duplicates, and issue rows before relying on totals."
    if status == ImportStatus.PASS:
        return "Ready for ledger review."
    if status == ImportStatus.PROCESSING:
        return "Wait for processing to complete."
    if report is None:
        return "Processing details are not available yet."
    return "Review import details."
