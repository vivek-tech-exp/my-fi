"""Repository helpers for canonical transaction persistence."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from decimal import Decimal
from typing import cast
from uuid import UUID

import duckdb

from app.db.database import database_connection
from app.models.ledger import CanonicalTransactionRecord

CANONICAL_TRANSACTIONS_BY_FILE_SQL = """
SELECT
    transaction_id,
    source_file_id,
    raw_row_id,
    bank_name,
    account_id,
    transaction_date,
    value_date,
    description_raw,
    amount,
    direction,
    balance,
    currency,
    source_row_number,
    reference_number,
    transaction_fingerprint,
    duplicate_confidence,
    created_at
FROM canonical_transactions
WHERE source_file_id = ?
ORDER BY source_row_number
"""

CANONICAL_TRANSACTIONS_COUNT_SQL = """
SELECT COUNT(*)
FROM canonical_transactions
WHERE source_file_id = ?
"""

CANONICAL_TRANSACTION_BY_FINGERPRINT_SQL = """
SELECT
    transaction_id,
    source_file_id,
    raw_row_id,
    bank_name,
    account_id,
    transaction_date,
    value_date,
    description_raw,
    amount,
    direction,
    balance,
    currency,
    source_row_number,
    reference_number,
    transaction_fingerprint,
    duplicate_confidence,
    created_at
FROM canonical_transactions
WHERE transaction_fingerprint = ?
LIMIT 1
"""

CANONICAL_TRANSACTION_DUPLICATE_CANDIDATES_SQL = """
SELECT
    transaction_id,
    source_file_id,
    raw_row_id,
    bank_name,
    account_id,
    transaction_date,
    value_date,
    description_raw,
    amount,
    direction,
    balance,
    currency,
    source_row_number,
    reference_number,
    transaction_fingerprint,
    duplicate_confidence,
    created_at
FROM canonical_transactions
WHERE bank_name = ?
  AND COALESCE(account_id, '') = ?
  AND transaction_date = ?
  AND direction = ?
  AND amount = ?
  AND transaction_fingerprint <> ?
ORDER BY created_at
"""


def insert_canonical_transactions(
    records: Sequence[CanonicalTransactionRecord],
    *,
    connection: duckdb.DuckDBPyConnection | None = None,
) -> None:
    """Persist a batch of canonical transactions."""

    if not records:
        return

    if connection is None:
        with database_connection() as new_connection:
            _insert_canonical_transactions(new_connection, records)
        return

    _insert_canonical_transactions(connection, records)


def get_canonical_transactions_by_file_id(
    file_id: UUID,
    *,
    connection: duckdb.DuckDBPyConnection | None = None,
) -> list[CanonicalTransactionRecord]:
    """Fetch canonical transactions for a source file."""

    if connection is None:
        with database_connection() as new_connection:
            return _fetch_canonical_transactions_by_file_id(new_connection, file_id)

    return _fetch_canonical_transactions_by_file_id(connection, file_id)


def get_canonical_transaction_count(
    file_id: UUID,
    *,
    connection: duckdb.DuckDBPyConnection | None = None,
) -> int:
    """Return the number of canonical transactions persisted for a source file."""

    if connection is None:
        with database_connection() as new_connection:
            return _fetch_canonical_transaction_count(new_connection, file_id)

    return _fetch_canonical_transaction_count(connection, file_id)


def delete_canonical_transactions_by_file_id(
    file_id: UUID,
    *,
    connection: duckdb.DuckDBPyConnection | None = None,
) -> None:
    """Delete canonical transactions for a file before reprocessing."""

    if connection is None:
        with database_connection() as new_connection:
            _delete_canonical_transactions_by_file_id(new_connection, file_id)
        return

    _delete_canonical_transactions_by_file_id(connection, file_id)


def get_canonical_transaction_by_fingerprint(
    transaction_fingerprint: str,
    *,
    connection: duckdb.DuckDBPyConnection | None = None,
) -> CanonicalTransactionRecord | None:
    """Fetch a canonical transaction by its duplicate-protection fingerprint."""

    if connection is None:
        with database_connection() as new_connection:
            return _fetch_canonical_transaction_by_fingerprint(
                new_connection,
                transaction_fingerprint,
            )

    return _fetch_canonical_transaction_by_fingerprint(connection, transaction_fingerprint)


def get_potential_duplicate_candidates(
    record: CanonicalTransactionRecord,
    *,
    connection: duckdb.DuckDBPyConnection | None = None,
) -> list[CanonicalTransactionRecord]:
    """Return same-account/date/direction/amount candidates for ambiguity checks."""

    if connection is None:
        with database_connection() as new_connection:
            return _fetch_potential_duplicate_candidates(new_connection, record)

    return _fetch_potential_duplicate_candidates(connection, record)


def _insert_canonical_transactions(
    connection: duckdb.DuckDBPyConnection,
    records: Sequence[CanonicalTransactionRecord],
) -> None:
    connection.executemany(
        """
        INSERT INTO canonical_transactions (
            transaction_id,
            source_file_id,
            raw_row_id,
            bank_name,
            account_id,
            transaction_date,
            value_date,
            description_raw,
            amount,
            direction,
            balance,
            currency,
            source_row_number,
            reference_number,
            transaction_fingerprint,
            duplicate_confidence,
            created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            [
                str(record.transaction_id),
                str(record.source_file_id),
                str(record.raw_row_id),
                record.bank_name,
                record.account_id,
                record.transaction_date,
                record.value_date,
                record.description_raw,
                record.amount,
                record.direction.value,
                record.balance,
                record.currency,
                record.source_row_number,
                record.reference_number,
                record.transaction_fingerprint,
                record.duplicate_confidence.value,
                _as_utc_naive(record.created_at),
            ]
            for record in records
        ],
    )


def _fetch_canonical_transactions_by_file_id(
    connection: duckdb.DuckDBPyConnection,
    file_id: UUID,
) -> list[CanonicalTransactionRecord]:
    rows = connection.execute(CANONICAL_TRANSACTIONS_BY_FILE_SQL, [str(file_id)]).fetchall()
    return [_row_to_canonical_transaction_record(row) for row in rows]


def _fetch_canonical_transaction_count(
    connection: duckdb.DuckDBPyConnection,
    file_id: UUID,
) -> int:
    row = connection.execute(CANONICAL_TRANSACTIONS_COUNT_SQL, [str(file_id)]).fetchone()
    if row is None:
        return 0

    return cast(int, row[0])


def _fetch_canonical_transaction_by_fingerprint(
    connection: duckdb.DuckDBPyConnection,
    transaction_fingerprint: str,
) -> CanonicalTransactionRecord | None:
    row = connection.execute(
        CANONICAL_TRANSACTION_BY_FINGERPRINT_SQL,
        [transaction_fingerprint],
    ).fetchone()
    if row is None:
        return None

    return _row_to_canonical_transaction_record(row)


def _fetch_potential_duplicate_candidates(
    connection: duckdb.DuckDBPyConnection,
    record: CanonicalTransactionRecord,
) -> list[CanonicalTransactionRecord]:
    rows = connection.execute(
        CANONICAL_TRANSACTION_DUPLICATE_CANDIDATES_SQL,
        [
            record.bank_name,
            record.account_id or "",
            record.transaction_date,
            record.direction.value,
            record.amount,
            record.transaction_fingerprint,
        ],
    ).fetchall()
    return [_row_to_canonical_transaction_record(row) for row in rows]


def _delete_canonical_transactions_by_file_id(
    connection: duckdb.DuckDBPyConnection,
    file_id: UUID,
) -> None:
    connection.execute(
        "DELETE FROM canonical_transactions WHERE source_file_id = ?",
        [str(file_id)],
    )


def _row_to_canonical_transaction_record(row: tuple[object, ...]) -> CanonicalTransactionRecord:
    return CanonicalTransactionRecord.model_validate(
        {
            "transaction_id": cast(str, row[0]),
            "source_file_id": cast(str, row[1]),
            "raw_row_id": cast(str, row[2]),
            "bank_name": cast(str, row[3]),
            "account_id": cast(str | None, row[4]),
            "transaction_date": row[5],
            "value_date": row[6],
            "description_raw": cast(str, row[7]),
            "amount": cast(Decimal, row[8]),
            "direction": cast(str, row[9]),
            "balance": cast(Decimal | None, row[10]),
            "currency": cast(str, row[11]),
            "source_row_number": cast(int, row[12]),
            "reference_number": cast(str | None, row[13]),
            "transaction_fingerprint": cast(str, row[14]),
            "duplicate_confidence": cast(str, row[15]),
            "created_at": _with_utc_timezone(cast(datetime, row[16])),
        }
    )


def _as_utc_naive(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value

    return value.astimezone(UTC).replace(tzinfo=None)


def _with_utc_timezone(value: datetime) -> datetime:
    if value.tzinfo is not None:
        return value.astimezone(UTC)

    return value.replace(tzinfo=UTC)
