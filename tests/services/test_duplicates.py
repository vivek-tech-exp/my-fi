"""Tests for canonical transaction duplicate protection."""

from datetime import date
from decimal import Decimal
from uuid import uuid4

from app.core.config import get_settings
from app.core.runtime import ensure_directories
from app.db.canonical_transactions import insert_canonical_transactions
from app.db.database import database_connection, initialize_database
from app.models.ledger import CanonicalTransactionRecord, TransactionDirection
from app.services.duplicates import apply_duplicate_protection


def test_duplicate_protection_marks_no_balance_match_as_probable_duplicate() -> None:
    settings = get_settings()
    ensure_directories(settings.required_directories)
    initialize_database()
    existing_transaction = _transaction(
        amount=Decimal("100.00"),
        balance=None,
        fingerprint="a" * 64,
    )
    duplicate_transaction = _transaction(
        amount=Decimal("100.00"),
        balance=None,
        fingerprint="a" * 64,
    )

    insert_canonical_transactions([existing_transaction])

    with database_connection() as connection:
        result = apply_duplicate_protection(
            [duplicate_transaction],
            connection=connection,
        )

    assert result.transactions_to_insert == []
    assert result.duplicate_transactions_detected == 1
    assert result.exact_duplicate_transactions == 0
    assert result.probable_duplicate_transactions == 1
    assert result.ambiguous_transactions_detected == 0


def _transaction(
    *,
    amount: Decimal,
    balance: Decimal | None,
    fingerprint: str,
) -> CanonicalTransactionRecord:
    return CanonicalTransactionRecord(
        transaction_id=uuid4(),
        source_file_id=uuid4(),
        raw_row_id=uuid4(),
        bank_name="kotak",
        account_id="travel-fund",
        transaction_date=date(2026, 4, 3),
        value_date=date(2026, 4, 3),
        description_raw="UPI/CAFE BREWSOME P/627219443204/resolve interna",
        amount=amount,
        direction=TransactionDirection.DEBIT,
        balance=balance,
        currency="INR",
        source_row_number=4,
        reference_number="UPI-609393884269",
        transaction_fingerprint=fingerprint,
    )
