"""Shared test factories for repository and service tests."""

from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from app.models.imports import BankName, ImportStatus, SourceFileRecord
from app.models.ledger import CanonicalTransactionRecord, TransactionDirection
from app.models.parsing import RawRowRecord, RawRowType
from app.models.validation import ValidationCheckStatus, ValidationReportRecord


def source_file_record(
    *,
    file_id: UUID | None = None,
    stored_path: str = "/tmp/statement.csv",
    bank_name: BankName = BankName.KOTAK,
    file_hash: str | None = None,
    import_status: ImportStatus = ImportStatus.RECEIVED,
    parser_version: str = "v1",
) -> SourceFileRecord:
    return SourceFileRecord(
        file_id=file_id or uuid4(),
        original_filename="statement.csv",
        stored_path=stored_path,
        bank_name=bank_name,
        account_id="primary",
        file_hash=file_hash or "a" * 64,
        file_size_bytes=10,
        uploaded_at=datetime(2026, 4, 1, tzinfo=UTC),
        parser_version=parser_version,
        import_status=import_status,
        encoding_detected="utf-8",
        delimiter_detected=",",
    )


def raw_row_record(
    *,
    file_id: UUID,
    row_type: RawRowType = RawRowType.ACCEPTED,
    row_number: int = 1,
    raw_payload: list[str] | None = None,
    header_row: bool = False,
) -> RawRowRecord:
    return RawRowRecord(
        raw_row_id=uuid4(),
        file_id=file_id,
        row_number=row_number,
        parser_name="test_parser",
        parser_version="v1",
        row_type=row_type,
        raw_text="raw,row",
        raw_payload=raw_payload,
        rejection_reason=None if row_type == RawRowType.ACCEPTED else "test_reason",
        header_row=header_row,
        repaired_row=False,
    )


def canonical_transaction(
    *,
    source_file_id: UUID | None = None,
    raw_row_id: UUID | None = None,
    bank_name: str = "kotak",
    account_id: str | None = "primary",
    transaction_date: date = date(2026, 4, 3),
    value_date: date | None = date(2026, 4, 3),
    description_raw: str = "UPI/CAFE BREWSOME",
    amount: Decimal = Decimal("100.00"),
    direction: TransactionDirection = TransactionDirection.DEBIT,
    balance: Decimal | None = Decimal("900.00"),
    source_row_number: int = 1,
    reference_number: str | None = "REF-1",
    fingerprint: str = "a" * 64,
    created_at: datetime | None = None,
) -> CanonicalTransactionRecord:
    return CanonicalTransactionRecord(
        transaction_id=uuid4(),
        source_file_id=source_file_id or uuid4(),
        raw_row_id=raw_row_id or uuid4(),
        bank_name=bank_name,
        account_id=account_id,
        transaction_date=transaction_date,
        value_date=value_date,
        description_raw=description_raw,
        amount=amount,
        direction=direction,
        balance=balance,
        currency="INR",
        source_row_number=source_row_number,
        reference_number=reference_number,
        transaction_fingerprint=fingerprint,
        created_at=created_at or datetime(2026, 4, 1, tzinfo=UTC),
    )


def validation_report(
    *,
    file_id: UUID,
    final_status: ImportStatus = ImportStatus.PASS,
    duplicate_rows: int = 0,
    generated_at: datetime | None = None,
) -> ValidationReportRecord:
    return ValidationReportRecord(
        report_id=uuid4(),
        file_id=file_id,
        total_rows=2,
        accepted_rows=1,
        ignored_rows=1,
        suspicious_rows=0,
        duplicate_rows=duplicate_rows,
        transactions_imported=1,
        reconciliation_status=ValidationCheckStatus.PASS,
        ledger_continuity_status=ValidationCheckStatus.PASS,
        final_status=final_status.value,
        messages=["ok"],
        generated_at=generated_at or datetime(2026, 4, 1, tzinfo=UTC),
    )
