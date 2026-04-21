"""Tests for import orchestration edge paths."""

from datetime import date
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import pytest
from app.core.config import get_settings
from app.core.runtime import ensure_directories
from app.db.database import database_connection, initialize_database
from app.models.imports import BankName, ImportStatus, PreParseNormalizationResult
from app.models.ledger import TransactionDirection
from app.models.parsing import ParserInspectionResult
from app.models.validation import ValidationCheckStatus
from app.parsers.base import BaseCsvParser
from app.services import imports as import_service
from tests.factories import source_file_record, validation_report


class AuditOnlyParser(BaseCsvParser):
    bank_name = BankName.HDFC
    parser_name = "audit_only_parser"
    supports_canonical_mapping = False

    def is_header_row(self, columns: list[str]) -> bool:
        return columns == ["Date", "Narration"]


def _initialize_storage() -> None:
    settings = get_settings()
    ensure_directories(settings.required_directories)
    initialize_database()


def _raise_runtime_error(message: str) -> None:
    raise RuntimeError(message)


def test_store_uploaded_csv_deletes_stored_file_when_insert_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _initialize_storage()
    settings = get_settings()

    def fail_insert(*_args, **_kwargs):
        return _raise_runtime_error("insert failed")

    monkeypatch.setattr(import_service, "insert_source_file", fail_insert)

    with pytest.raises(RuntimeError, match="insert failed"):
        import_service.store_uploaded_csv(
            file_bytes=b"Date,Narration\n2026-04-01,Cafe\n",
            original_filename="../bad name.csv",
            bank_name=BankName.HDFC,
            account_id=None,
        )

    assert list(settings.uploads_dir.rglob("*bad_name.csv")) == []


def test_store_uploaded_csv_handles_concurrent_duplicate_registration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = get_settings()
    ensure_directories(settings.required_directories)
    existing_record = source_file_record(
        file_hash="0" * 64,
        stored_path=str(settings.uploads_dir / "existing.csv"),
    )
    lookup_results = iter([None, existing_record])

    def next_lookup(*_args):
        return next(lookup_results)

    def fail_insert(*_args, **_kwargs):
        return _raise_runtime_error("duplicate race")

    monkeypatch.setattr(import_service, "get_source_file_by_hash", next_lookup)
    monkeypatch.setattr(import_service, "insert_source_file", fail_insert)
    monkeypatch.setattr(
        import_service,
        "_build_duplicate_upload_response",
        lambda record: import_service.UploadCsvResponse.from_source_file_record(
            record,
            parser_name="kotak_csv_parser",
            duplicate_file=True,
            message="duplicate",
        ),
    )

    response = import_service.store_uploaded_csv(
        file_bytes=b"Date,Narration\n2026-04-01,Cafe\n",
        original_filename="race.csv",
        bank_name=BankName.KOTAK,
        account_id=None,
    )

    assert response.duplicate_file is True
    assert list(settings.uploads_dir.rglob("*race.csv")) == []


def test_reprocess_rolls_back_when_processing_fails(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _initialize_storage()
    stored_file = tmp_path / "statement.csv"
    stored_file.write_text("Date,Narration\n2026-04-01,Cafe\n", encoding="utf-8")
    record = source_file_record(
        file_id=uuid4(),
        file_hash="4" * 64,
        bank_name=BankName.HDFC,
        stored_path=str(stored_file),
    )
    with database_connection() as connection:
        connection.execute("BEGIN TRANSACTION")
        import_service.insert_source_file(record, connection=connection)
        connection.execute("COMMIT")

    def fail_delete(*_args, **_kwargs):
        return _raise_runtime_error("delete failed")

    monkeypatch.setattr(import_service, "delete_raw_rows_by_file_id", fail_delete)

    with pytest.raises(RuntimeError, match="delete failed"):
        import_service.reprocess_import(record.file_id)


def test_process_source_file_keeps_audit_only_status_without_canonical_mapping() -> None:
    _initialize_storage()
    parser = AuditOnlyParser(parser_version="v1")
    source_file = source_file_record(
        file_id=uuid4(),
        file_hash="5" * 64,
        bank_name=BankName.HDFC,
        import_status=ImportStatus.RECEIVED,
    )
    normalization_result = PreParseNormalizationResult(
        normalized_text="Date,Narration\n2026-04-01,Cafe\n",
        encoding_detected="utf-8",
        delimiter_detected=",",
    )

    with database_connection() as connection:
        connection.execute("BEGIN TRANSACTION")
        source_file = import_service.insert_source_file(source_file, connection=connection)
        persisted_record, inspection_result, report = import_service._process_source_file_record(
            source_file=source_file,
            parser=parser,
            normalization_result=normalization_result,
            account_id=None,
            connection=connection,
        )
        connection.execute("COMMIT")

    assert persisted_record.import_status == ImportStatus.RECEIVED
    assert inspection_result.transactions_imported == 0
    assert report.final_status == "PASS"


def test_import_message_builder_covers_warning_and_scaffolding_paths() -> None:
    duplicate_only_result = ParserInspectionResult(
        parser_name="test",
        parser_version="v1",
        duplicate_transactions_detected=2,
    )
    suspicious_result = ParserInspectionResult(
        parser_name="test",
        parser_version="v1",
        suspicious_rows_recorded=1,
    )
    clean_result = ParserInspectionResult(parser_name="test", parser_version="v1")
    failed_report = validation_report(file_id=uuid4(), final_status=ImportStatus.FAIL_NEEDS_REVIEW)
    clean_report = validation_report(file_id=uuid4())

    assert (
        import_service._inspect_normalized_file(
            file_id=uuid4(),
            parser=AuditOnlyParser(parser_version="v1"),
            normalized_text=None,
            delimiter=None,
            account_id=None,
        ).raw_rows_recorded
        == 0
    )
    assert import_service._sanitize_filename(" ../.. ") == "upload.csv"
    assert import_service._sanitize_filename("") == "upload.csv"
    assert import_service._build_upload_message(
        quarantine_required=False,
        inspection_result=clean_result,
        supports_canonical_mapping=True,
        validation_report=failed_report,
    ).startswith("File parsed but failed validation")
    assert "duplicate transactions were skipped" in import_service._build_upload_message(
        quarantine_required=False,
        inspection_result=duplicate_only_result,
        supports_canonical_mapping=True,
        validation_report=clean_report,
    )
    assert "suspicious rows were flagged" in import_service._build_upload_message(
        quarantine_required=False,
        inspection_result=suspicious_result,
        supports_canonical_mapping=False,
        validation_report=clean_report,
    )
    assert "parser scaffolding captured" in import_service._build_upload_message(
        quarantine_required=False,
        inspection_result=clean_result,
        supports_canonical_mapping=False,
        validation_report=clean_report,
    )
    suspicious_canonical_result = ParserInspectionResult(
        parser_name="test",
        parser_version="v1",
        suspicious_rows_recorded=1,
        canonical_transactions=[
            import_service.get_bank_parser(
                bank_name=BankName.HDFC,
                parser_version="v1",
            ).build_canonical_transaction(
                source_file_id=uuid4(),
                raw_row_id=uuid4(),
                account_id=None,
                transaction_date=date(2026, 4, 1),
                value_date=None,
                description_raw="Cafe",
                amount=Decimal("1.00"),
                direction=TransactionDirection.DEBIT,
                balance=None,
                source_row_number=1,
                reference_number=None,
            )
        ],
    )
    assert "with warnings" in import_service._build_upload_message(
        quarantine_required=False,
        inspection_result=suspicious_canonical_result,
        supports_canonical_mapping=True,
        validation_report=clean_report,
    )
    assert clean_report.reconciliation_status == ValidationCheckStatus.PASS
