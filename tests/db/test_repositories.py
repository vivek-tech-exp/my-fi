"""Repository tests for DuckDB persistence helpers."""

from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest
from app.core.config import get_settings
from app.core.runtime import ensure_directories
from app.db import canonical_transactions as canonical_repo
from app.db import raw_rows as raw_rows_repo
from app.db import source_files as source_files_repo
from app.db import validation_reports as validation_reports_repo
from app.db.database import database_connection, initialize_database
from app.models.imports import BankName, ImportStatus
from app.models.ledger import TransactionDirection, TransactionSummaryGroupBy
from app.models.parsing import RawRowType
from tests.factories import (
    canonical_transaction,
    raw_row_record,
    source_file_record,
    validation_report,
)


def _initialize_storage() -> None:
    settings = get_settings()
    ensure_directories(settings.required_directories)
    initialize_database()


def test_source_file_repository_round_trips_and_updates_records() -> None:
    _initialize_storage()
    file_id = uuid4()
    record = source_file_record(
        file_id=file_id,
        file_hash="1" * 64,
        bank_name=BankName.HDFC,
    )

    inserted = source_files_repo.insert_source_file(record)
    by_id = source_files_repo.get_source_file_by_id(file_id)
    by_hash = source_files_repo.get_source_file_by_hash("1" * 64)
    listed = source_files_repo.list_source_files()
    updated = source_files_repo.update_source_file_processing_result(
        file_id=file_id,
        import_status=ImportStatus.PASS_WITH_WARNINGS,
        statement_start_date=None,
        statement_end_date=None,
    )
    reparsed = source_files_repo.update_source_file_processing_result(
        file_id=file_id,
        import_status=ImportStatus.PASS,
        statement_start_date=None,
        statement_end_date=None,
        account_id="generated-account-id",
        parser_version="v2",
    )

    assert inserted.file_id == file_id
    assert by_id.file_id == file_id
    assert by_hash is not None
    assert by_hash.file_id == file_id
    assert listed[0].file_id == file_id
    assert updated.import_status == ImportStatus.PASS_WITH_WARNINGS
    assert updated.parser_version == "v1"
    assert reparsed.import_status == ImportStatus.PASS
    assert reparsed.account_id == "generated-account-id"
    assert reparsed.parser_version == "v2"
    assert source_files_repo.get_source_file_by_hash("2" * 64) is None
    with pytest.raises(LookupError):
        source_files_repo.get_source_file_by_id(uuid4())

    with database_connection() as connection:
        assert source_files_repo.get_source_file_by_hash("missing", connection=connection) is None
        assert source_files_repo.list_source_files(connection=connection)[0].file_id == file_id

    assert source_files_repo._as_utc_naive(datetime(2026, 4, 1)) == datetime(2026, 4, 1)
    assert source_files_repo._with_utc_timezone(datetime(2026, 4, 1, tzinfo=UTC)).tzinfo == UTC


def test_raw_row_repository_round_trips_summarizes_and_deletes_rows() -> None:
    _initialize_storage()
    file_id = uuid4()
    raw_rows_repo.insert_raw_rows([])
    rows = [
        raw_row_record(
            file_id=file_id,
            row_type=RawRowType.IGNORED,
            row_number=1,
            raw_payload=["Date", "Narration"],
            header_row=True,
        ),
        raw_row_record(file_id=file_id, row_type=RawRowType.ACCEPTED, row_number=2),
        raw_row_record(file_id=file_id, row_type=RawRowType.SUSPICIOUS, row_number=3),
    ]

    raw_rows_repo.insert_raw_rows(rows)
    summary = raw_rows_repo.get_raw_row_audit_summary(file_id)
    fetched_rows = raw_rows_repo.get_raw_rows_by_file_id(file_id)
    raw_rows_repo.delete_raw_rows_by_file_id(file_id)

    assert summary.header_detected is True
    assert summary.raw_rows_recorded == 3
    assert summary.accepted_rows_recorded == 1
    assert summary.ignored_rows_recorded == 1
    assert summary.suspicious_rows_recorded == 1
    assert fetched_rows[0].raw_payload == ["Date", "Narration"]
    assert raw_rows_repo.get_raw_rows_by_file_id(file_id) == []

    with database_connection() as connection:
        assert raw_rows_repo.get_raw_row_audit_summary(
            file_id, connection=connection
        ).raw_rows_recorded == (0)
        assert raw_rows_repo.get_raw_rows_by_file_id(file_id, connection=connection) == []
        raw_rows_repo.delete_raw_rows_by_file_id(file_id, connection=connection)

    class EmptyRawSummaryConnection:
        def execute(self, *_args):
            return self

        def fetchone(self):
            return None

    assert (
        raw_rows_repo._fetch_raw_row_audit_summary(
            EmptyRawSummaryConnection(),
            uuid4(),
        ).raw_rows_recorded
        == 0
    )


def test_canonical_transaction_repository_round_trips_and_deletes_rows() -> None:
    _initialize_storage()
    file_id = uuid4()
    transaction = canonical_transaction(
        source_file_id=file_id,
        bank_name="hdfc",
        account_id="primary",
        transaction_date=datetime(2026, 4, 1).date(),
        amount=Decimal("250.00"),
        fingerprint="3" * 64,
        created_at=datetime(2026, 4, 1),
    )
    second_transaction = canonical_transaction(
        source_file_id=uuid4(),
        bank_name="federal",
        account_id="secondary",
        transaction_date=datetime(2026, 4, 2).date(),
        amount=Decimal("125.00"),
        direction=TransactionDirection.CREDIT,
        fingerprint="5" * 64,
        created_at=datetime(2026, 4, 2),
    )
    duplicate_candidate = canonical_transaction(
        source_file_id=uuid4(),
        bank_name="hdfc",
        account_id="primary",
        transaction_date=datetime(2026, 4, 1).date(),
        amount=Decimal("250.00"),
        fingerprint="4" * 64,
    )

    canonical_repo.insert_canonical_transactions([])
    canonical_repo.insert_canonical_transactions([transaction, second_transaction])

    assert canonical_repo.get_canonical_transaction_count(file_id) == 1
    assert canonical_repo.get_canonical_transactions_by_file_id(file_id)[0].amount == Decimal(
        "250.00"
    )
    assert len(canonical_repo.list_canonical_transactions(limit=10, offset=0)) == 2
    assert (
        canonical_repo.list_canonical_transactions(
            direction=TransactionDirection.CREDIT,
            limit=10,
            offset=0,
        )[0].transaction_fingerprint
        == "5" * 64
    )
    assert (
        canonical_repo.list_canonical_transactions(
            bank_name="hdfc",
            account_id="primary",
            transaction_date_from=datetime(2026, 4, 1).date(),
            transaction_date_to=datetime(2026, 4, 1).date(),
            limit=10,
            offset=0,
        )[0].transaction_fingerprint
        == "3" * 64
    )
    assert (
        canonical_repo.get_canonical_transaction_by_fingerprint("3" * 64).transaction_fingerprint
        == "3" * 64
    )
    assert canonical_repo.get_canonical_transaction_by_fingerprint("9" * 64) is None
    assert canonical_repo.get_potential_duplicate_candidates(duplicate_candidate)[0].amount == (
        Decimal("250.00")
    )
    with database_connection() as connection:
        assert (
            canonical_repo.get_canonical_transactions_by_file_id(
                file_id,
                connection=connection,
            )[0].transaction_fingerprint
            == "3" * 64
        )
        assert canonical_repo.get_canonical_transaction_count(file_id, connection=connection) == 1
        assert (
            canonical_repo.list_canonical_transactions(
                source_file_id=file_id,
                limit=10,
                offset=0,
                connection=connection,
            )[0].transaction_fingerprint
            == "3" * 64
        )
        summary_rows = canonical_repo.summarize_canonical_transactions(
            group_by=TransactionSummaryGroupBy.MONTH,
            direction=TransactionDirection.DEBIT,
            limit=10,
            offset=0,
            connection=connection,
        )
        canonical_repo.delete_canonical_transactions_by_file_id(file_id, connection=connection)
    assert summary_rows[0].transaction_count == 1
    assert summary_rows[0].debit_total == Decimal("250.00")
    assert summary_rows[0].credit_total == Decimal("0.00")
    assert summary_rows[0].net_amount == Decimal("-250.00")

    canonical_repo.delete_canonical_transactions_by_file_id(file_id)

    assert canonical_repo.get_canonical_transaction_count(file_id) == 0
    assert canonical_repo._with_utc_timezone(datetime(2026, 4, 1, tzinfo=UTC)).tzinfo == UTC

    class EmptyCountConnection:
        def execute(self, *_args):
            return self

        def fetchone(self):
            return None

    assert canonical_repo._fetch_canonical_transaction_count(EmptyCountConnection(), uuid4()) == 0
    with pytest.raises(ValueError):
        canonical_repo._date_bucket_expression("year")  # type: ignore[arg-type]


def test_validation_report_repository_round_trips_latest_report(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _initialize_storage()
    file_id = uuid4()
    first_report = validation_report(file_id=file_id)
    second_report = validation_report(
        file_id=file_id,
        final_status=ImportStatus.PASS_WITH_WARNINGS,
        duplicate_rows=2,
        generated_at=datetime(2026, 4, 2, tzinfo=UTC),
    )

    validation_reports_repo.upsert_validation_report(first_report)
    latest_report = validation_reports_repo.upsert_validation_report(second_report)

    assert latest_report.final_status == "PASS_WITH_WARNINGS"
    assert validation_reports_repo.get_validation_report_by_file_id(file_id).duplicate_rows == 2
    assert validation_reports_repo.get_validation_report_by_file_id(uuid4()) is None
    assert validation_reports_repo._with_utc_timezone(datetime(2026, 4, 1, tzinfo=UTC)).tzinfo == (
        UTC
    )
    assert validation_reports_repo._as_utc_naive(datetime(2026, 4, 1)) == datetime(2026, 4, 1)
    with database_connection() as connection:
        assert (
            validation_reports_repo.get_validation_report_by_file_id(
                file_id,
                connection=connection,
            ).duplicate_rows
            == 2
        )

    monkeypatch.setattr(
        validation_reports_repo,
        "_fetch_validation_report_by_file_id",
        lambda *_: None,
    )
    with database_connection() as connection, pytest.raises(LookupError):
        validation_reports_repo._upsert_validation_report(
            connection,
            validation_report(file_id=uuid4()),
        )
