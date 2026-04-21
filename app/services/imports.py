"""Services for source-file intake and local storage."""

from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from re import sub
from uuid import UUID, uuid4

import duckdb

from app.core.config import get_settings
from app.db.canonical_transactions import (
    delete_canonical_transactions_by_file_id,
    get_canonical_transaction_count,
    insert_canonical_transactions,
)
from app.db.database import database_connection
from app.db.raw_rows import (
    delete_raw_rows_by_file_id,
    get_raw_row_audit_summary,
    insert_raw_rows,
)
from app.db.source_files import (
    get_source_file_by_hash,
    get_source_file_by_id,
    insert_source_file,
    update_source_file_processing_result,
)
from app.db.validation_reports import get_validation_report_by_file_id, upsert_validation_report
from app.models.imports import (
    BankName,
    ImportStatus,
    PreParseNormalizationResult,
    SourceFileRecord,
    UploadCsvResponse,
)
from app.models.parsing import ParserInspectionResult
from app.models.validation import ValidationReportRecord
from app.parsers import get_bank_parser
from app.parsers.base import BaseCsvParser
from app.services.duplicates import apply_duplicate_protection
from app.services.normalization import normalize_uploaded_csv
from app.services.validation import build_validation_report


def store_uploaded_csv(
    *,
    file_bytes: bytes,
    original_filename: str,
    bank_name: BankName,
    account_id: str | None,
) -> UploadCsvResponse:
    """Persist an uploaded CSV file and return its initial import metadata."""

    settings = get_settings()
    parser = get_bank_parser(
        bank_name=bank_name,
        parser_version=settings.default_parser_version,
    )
    file_hash = sha256(file_bytes).hexdigest()
    existing_record = get_source_file_by_hash(file_hash)
    if existing_record is not None:
        return _build_duplicate_upload_response(existing_record)

    file_id = uuid4()
    normalization_result = normalize_uploaded_csv(file_bytes)
    destination_root = (
        settings.quarantine_dir
        if normalization_result.quarantine_required
        else settings.uploads_dir
    )
    sanitized_filename = _sanitize_filename(original_filename)
    destination_dir = destination_root / bank_name.value / file_hash[:2]
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
        parser_version=parser.parser_version,
        import_status=(
            ImportStatus.FAIL_NEEDS_REVIEW
            if normalization_result.quarantine_required
            else (
                ImportStatus.PROCESSING
                if parser.supports_canonical_mapping
                else ImportStatus.RECEIVED
            )
        ),
        encoding_detected=normalization_result.encoding_detected,
        delimiter_detected=normalization_result.delimiter_detected,
    )
    inspection_result = ParserInspectionResult(
        parser_name=parser.parser_name,
        parser_version=parser.parser_version,
    )

    try:
        with database_connection() as connection:
            connection.execute("BEGIN TRANSACTION")
            try:
                source_file = insert_source_file(source_file, connection=connection)
                persisted_record, inspection_result, validation_report = (
                    _process_source_file_record(
                        source_file=source_file,
                        parser=parser,
                        normalization_result=normalization_result,
                        account_id=account_id,
                        connection=connection,
                    )
                )
                connection.execute("COMMIT")
            except Exception:
                connection.execute("ROLLBACK")
                raise
    except Exception:
        existing_record = get_source_file_by_hash(file_hash)
        if existing_record is not None:
            if stored_path != Path(existing_record.stored_path):
                stored_path.unlink(missing_ok=True)

            return _build_duplicate_upload_response(existing_record)

        stored_path.unlink(missing_ok=True)
        raise

    return UploadCsvResponse.from_source_file_record(
        persisted_record,
        parser_name=parser.parser_name,
        audit_summary=inspection_result,
        transactions_imported=inspection_result.transactions_imported,
        duplicate_transactions_detected=inspection_result.duplicate_transactions_detected,
        exact_duplicate_transactions=inspection_result.exact_duplicate_transactions,
        probable_duplicate_transactions=inspection_result.probable_duplicate_transactions,
        ambiguous_transactions_detected=inspection_result.ambiguous_transactions_detected,
        duplicate_file=False,
        message=_build_upload_message(
            quarantine_required=normalization_result.quarantine_required,
            inspection_result=inspection_result,
            supports_canonical_mapping=parser.supports_canonical_mapping,
            validation_report=validation_report,
        ),
    )


def reprocess_import(file_id: UUID) -> UploadCsvResponse:
    """Re-run parser and validation logic for a stored source file."""

    settings = get_settings()
    source_file = get_source_file_by_id(file_id)
    stored_path = Path(source_file.stored_path)
    if not stored_path.exists():
        raise FileNotFoundError(f"Stored source file '{source_file.stored_path}' was not found.")

    parser = get_bank_parser(
        bank_name=source_file.bank_name,
        parser_version=settings.default_parser_version,
    )
    normalization_result = normalize_uploaded_csv(stored_path.read_bytes())

    with database_connection() as connection:
        connection.execute("BEGIN TRANSACTION")
        try:
            delete_raw_rows_by_file_id(file_id, connection=connection)
            delete_canonical_transactions_by_file_id(file_id, connection=connection)
            persisted_record, inspection_result, validation_report = _process_source_file_record(
                source_file=source_file,
                parser=parser,
                normalization_result=normalization_result,
                account_id=source_file.account_id,
                connection=connection,
            )
            connection.execute("COMMIT")
        except Exception:
            connection.execute("ROLLBACK")
            raise

    return UploadCsvResponse.from_source_file_record(
        persisted_record,
        parser_name=parser.parser_name,
        audit_summary=inspection_result,
        transactions_imported=inspection_result.transactions_imported,
        duplicate_transactions_detected=inspection_result.duplicate_transactions_detected,
        exact_duplicate_transactions=inspection_result.exact_duplicate_transactions,
        probable_duplicate_transactions=inspection_result.probable_duplicate_transactions,
        ambiguous_transactions_detected=inspection_result.ambiguous_transactions_detected,
        duplicate_file=False,
        message=_build_upload_message(
            quarantine_required=normalization_result.quarantine_required,
            inspection_result=inspection_result,
            supports_canonical_mapping=parser.supports_canonical_mapping,
            validation_report=validation_report,
            reprocessed=True,
        ),
    )


def _process_source_file_record(
    *,
    source_file: SourceFileRecord,
    parser: BaseCsvParser,
    normalization_result: PreParseNormalizationResult,
    account_id: str | None,
    connection: duckdb.DuckDBPyConnection,
) -> tuple[SourceFileRecord, ParserInspectionResult, ValidationReportRecord]:
    inspection_result = _inspect_normalized_file(
        file_id=source_file.file_id,
        parser=parser,
        normalized_text=normalization_result.normalized_text,
        delimiter=normalization_result.delimiter_detected,
        account_id=account_id,
    )
    insert_raw_rows(inspection_result.raw_rows, connection=connection)
    if parser.supports_canonical_mapping and inspection_result.canonical_transactions:
        duplicate_result = apply_duplicate_protection(
            inspection_result.canonical_transactions,
            connection=connection,
        )
        inspection_result.canonical_transactions = duplicate_result.transactions_to_insert
        inspection_result.exact_duplicate_transactions = (
            duplicate_result.exact_duplicate_transactions
        )
        inspection_result.probable_duplicate_transactions = (
            duplicate_result.probable_duplicate_transactions
        )
        inspection_result.ambiguous_transactions_detected = (
            duplicate_result.ambiguous_transactions_detected
        )
        inspection_result.duplicate_transactions_detected = (
            duplicate_result.duplicate_transactions_detected
        )
        insert_canonical_transactions(
            inspection_result.canonical_transactions,
            connection=connection,
        )

    validation_report = build_validation_report(
        file_id=source_file.file_id,
        inspection_result=inspection_result,
        supports_canonical_mapping=parser.supports_canonical_mapping,
        quarantine_required=normalization_result.quarantine_required,
        normalization_failure_reason=normalization_result.failure_reason,
    )
    upsert_validation_report(validation_report, connection=connection)

    persisted_record = source_file
    if parser.supports_canonical_mapping or normalization_result.quarantine_required:
        persisted_record = update_source_file_processing_result(
            file_id=source_file.file_id,
            import_status=ImportStatus(validation_report.final_status),
            statement_start_date=inspection_result.statement_start_date,
            statement_end_date=inspection_result.statement_end_date,
            parser_version=parser.parser_version,
            connection=connection,
        )

    return persisted_record, inspection_result, validation_report


def _build_duplicate_upload_response(record: SourceFileRecord) -> UploadCsvResponse:
    existing_parser = get_bank_parser(
        bank_name=record.bank_name,
        parser_version=record.parser_version,
    )
    validation_report = get_validation_report_by_file_id(record.file_id)
    return UploadCsvResponse.from_source_file_record(
        record,
        parser_name=existing_parser.parser_name,
        audit_summary=get_raw_row_audit_summary(record.file_id),
        transactions_imported=get_canonical_transaction_count(record.file_id),
        duplicate_transactions_detected=(
            validation_report.duplicate_rows if validation_report is not None else 0
        ),
        duplicate_file=True,
        message="Matching file already registered. Returning existing import metadata.",
    )


def _sanitize_filename(filename: str) -> str:
    """Return a filesystem-safe filename while preserving readability."""

    raw_name = Path(filename).name.strip()
    if not raw_name:
        return "upload.csv"

    cleaned_name = sub(r"[^A-Za-z0-9._-]+", "_", raw_name)
    return cleaned_name.strip("._") or "upload.csv"


def _inspect_normalized_file(
    *,
    file_id: UUID,
    parser: BaseCsvParser,
    normalized_text: str | None,
    delimiter: str | None,
    account_id: str | None,
) -> ParserInspectionResult:
    if normalized_text is None:
        return ParserInspectionResult(
            parser_name=parser.parser_name,
            parser_version=parser.parser_version,
        )

    return parser.inspect_text(
        file_id=file_id,
        normalized_text=normalized_text,
        delimiter=delimiter,
        account_id=account_id,
    )


def _build_upload_message(
    *,
    quarantine_required: bool,
    inspection_result: ParserInspectionResult,
    supports_canonical_mapping: bool,
    validation_report: ValidationReportRecord,
    reprocessed: bool = False,
) -> str:
    prefix = "File reprocessed" if reprocessed else "File parsed"

    if quarantine_required:
        return (
            "File was quarantined after normalization failed. Review the source file before "
            "attempting parser execution."
        )

    if validation_report.final_status == ImportStatus.FAIL_NEEDS_REVIEW.value:
        return "File parsed but failed validation. Review the import report before trusting it."

    if supports_canonical_mapping and inspection_result.transactions_imported > 0:
        if (
            inspection_result.duplicate_transactions_detected > 0
            or inspection_result.ambiguous_transactions_detected > 0
        ):
            return (
                f"{prefix} and {inspection_result.transactions_imported} new transactions "
                "were imported into the canonical ledger with duplicate warnings."
            )

        if inspection_result.suspicious_rows_recorded > 0:
            return (
                f"{prefix} and {inspection_result.transactions_imported} transactions were "
                "imported into the canonical ledger with warnings."
            )

        return (
            f"{prefix} and {inspection_result.transactions_imported} transactions were "
            "imported into the canonical ledger."
        )

    if supports_canonical_mapping and inspection_result.duplicate_transactions_detected > 0:
        return (
            "File parsed successfully, but no new transactions were imported because "
            f"{inspection_result.duplicate_transactions_detected} duplicate transactions "
            "were skipped."
        )

    if inspection_result.suspicious_rows_recorded > 0:
        return (
            "File stored locally, raw rows were audited, and suspicious rows were flagged "
            "for review before bank-specific transaction mapping is introduced."
        )

    return (
        "File stored locally, raw rows were audited, and parser scaffolding captured "
        "header and row metadata for later canonical mapping."
    )
