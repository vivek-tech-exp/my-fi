"""Tests for canonical transaction duplicate protection."""

from datetime import date
from decimal import Decimal
from uuid import uuid4

from app.core.config import get_settings
from app.core.runtime import ensure_directories
from app.db.canonical_transactions import insert_canonical_transactions
from app.db.database import database_connection, initialize_database
from app.models.ledger import CanonicalTransactionRecord, TransactionDirection
from app.services.duplicates import (
    _is_ambiguous_match,
    _normalized_description,
    apply_duplicate_protection,
)


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


def test_duplicate_protection_marks_in_batch_balance_match_as_exact_duplicate() -> None:
    settings = get_settings()
    ensure_directories(settings.required_directories)
    initialize_database()
    first_transaction = _transaction(
        amount=Decimal("100.00"),
        balance=Decimal("900.00"),
        fingerprint="b" * 64,
    )
    second_transaction = _transaction(
        amount=Decimal("100.00"),
        balance=Decimal("900.00"),
        fingerprint="b" * 64,
    )

    with database_connection() as connection:
        result = apply_duplicate_protection(
            [first_transaction, second_transaction],
            connection=connection,
        )

    assert result.transactions_to_insert == [first_transaction]
    assert result.duplicate_transactions_detected == 1
    assert result.exact_duplicate_transactions == 1
    assert result.probable_duplicate_transactions == 0


def test_duplicate_protection_marks_no_balance_existing_candidate_as_ambiguous() -> None:
    settings = get_settings()
    ensure_directories(settings.required_directories)
    initialize_database()
    existing_transaction = _transaction(
        amount=Decimal("100.00"),
        balance=None,
        fingerprint="c" * 64,
    )
    ambiguous_transaction = _transaction(
        amount=Decimal("100.00"),
        balance=None,
        fingerprint="d" * 64,
    )

    insert_canonical_transactions([existing_transaction])

    with database_connection() as connection:
        result = apply_duplicate_protection(
            [ambiguous_transaction],
            connection=connection,
        )

    assert result.transactions_to_insert[0].duplicate_confidence == "AMBIGUOUS"
    assert result.ambiguous_transactions_detected == 1
    assert result.duplicate_transactions_detected == 0


def test_duplicate_protection_treats_balance_mismatch_as_unique() -> None:
    settings = get_settings()
    ensure_directories(settings.required_directories)
    initialize_database()
    existing_transaction = _transaction(
        amount=Decimal("100.00"),
        balance=Decimal("900.00"),
        fingerprint="c" * 64,
    )
    unique_transaction = _transaction(
        amount=Decimal("100.00"),
        balance=Decimal("800.00"),
        fingerprint="d" * 64,
    )

    insert_canonical_transactions([existing_transaction])

    with database_connection() as connection:
        result = apply_duplicate_protection(
            [unique_transaction],
            connection=connection,
        )

    assert result.transactions_to_insert == [unique_transaction]
    assert result.ambiguous_transactions_detected == 0
    assert result.duplicate_transactions_detected == 0


def test_ambiguous_match_rejects_mismatched_candidates() -> None:
    transaction = _transaction(
        amount=Decimal("100.00"),
        balance=Decimal("900.00"),
        fingerprint="e" * 64,
    )

    assert _is_ambiguous_match(transaction, transaction) is False
    bank_mismatch = transaction.model_copy(
        update={"bank_name": "hdfc", "transaction_fingerprint": "f" * 64}
    )
    assert _is_ambiguous_match(transaction, bank_mismatch) is False
    assert (
        _is_ambiguous_match(
            transaction,
            transaction.model_copy(
                update={
                    "transaction_fingerprint": "f" * 64,
                    "reference_number": "REF-DIFFERENT",
                    "description_raw": "UPI / cafe brewsome p 627219443204 resolve interna",
                }
            ),
        )
        is True
    )
    assert (
        _is_ambiguous_match(
            transaction,
            transaction.model_copy(
                update={
                    "transaction_fingerprint": "f" * 64,
                    "reference_number": "REF-DIFFERENT",
                    "description_raw": "different",
                }
            ),
        )
        is False
    )
    assert (
        _is_ambiguous_match(
            transaction,
            transaction.model_copy(
                update={
                    "transaction_fingerprint": "f" * 64,
                    "reference_number": "UPI-609393884269",
                    "description_raw": "different",
                }
            ),
        )
        is True
    )
    assert _normalized_description("UPI / Cafe   Brewsome!!") == "upi cafe brewsome"


def test_ambiguous_match_rejects_other_mismatches() -> None:
    transaction = _transaction(
        amount=Decimal("100.00"),
        balance=Decimal("900.00"),
        fingerprint="e" * 64,
    )

    assert _is_ambiguous_match(
        transaction,
        transaction.model_copy(update={"account_id": "other", "transaction_fingerprint": "f" * 64}),
    ) is (False)
    assert (
        _is_ambiguous_match(
            transaction,
            transaction.model_copy(
                update={
                    "transaction_date": date(2026, 4, 4),
                    "transaction_fingerprint": "f" * 64,
                }
            ),
        )
        is False
    )
    assert (
        _is_ambiguous_match(
            transaction,
            transaction.model_copy(
                update={
                    "direction": TransactionDirection.CREDIT,
                    "transaction_fingerprint": "f" * 64,
                }
            ),
        )
        is False
    )
    assert (
        _is_ambiguous_match(
            transaction,
            transaction.model_copy(
                update={
                    "amount": Decimal("101.00"),
                    "transaction_fingerprint": "f" * 64,
                }
            ),
        )
        is False
    )


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
