"""Repository helpers for canonical transaction persistence."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import cast
from uuid import UUID

import duckdb

from app.db.database import database_connection
from app.models.ledger import (
    CanonicalTransactionRecord,
    CanonicalTransactionViewRecord,
    DuplicateConfidence,
    TransactionDirection,
    TransactionSummaryGroupBy,
    TransactionSummaryRecord,
)

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


def list_canonical_transactions(
    *,
    bank_name: str | None = None,
    account_id: str | None = None,
    source_file_id: UUID | None = None,
    direction: TransactionDirection | None = None,
    description_contains: str | None = None,
    amount_min: Decimal | None = None,
    amount_max: Decimal | None = None,
    duplicate_confidence: DuplicateConfidence | None = None,
    has_balance: bool | None = None,
    transaction_date_from: date | None = None,
    transaction_date_to: date | None = None,
    limit: int = 100,
    offset: int = 0,
    connection: duckdb.DuckDBPyConnection | None = None,
) -> list[CanonicalTransactionViewRecord]:
    """List canonical transactions with optional filters and pagination."""

    if connection is None:
        with database_connection() as new_connection:
            return _list_canonical_transactions(
                new_connection,
                bank_name=bank_name,
                account_id=account_id,
                source_file_id=source_file_id,
                direction=direction,
                description_contains=description_contains,
                amount_min=amount_min,
                amount_max=amount_max,
                duplicate_confidence=duplicate_confidence,
                has_balance=has_balance,
                transaction_date_from=transaction_date_from,
                transaction_date_to=transaction_date_to,
                limit=limit,
                offset=offset,
            )

    return _list_canonical_transactions(
        connection,
        bank_name=bank_name,
        account_id=account_id,
        source_file_id=source_file_id,
        direction=direction,
        description_contains=description_contains,
        amount_min=amount_min,
        amount_max=amount_max,
        duplicate_confidence=duplicate_confidence,
        has_balance=has_balance,
        transaction_date_from=transaction_date_from,
        transaction_date_to=transaction_date_to,
        limit=limit,
        offset=offset,
    )


def count_canonical_transactions(
    *,
    bank_name: str | None = None,
    account_id: str | None = None,
    source_file_id: UUID | None = None,
    direction: TransactionDirection | None = None,
    description_contains: str | None = None,
    amount_min: Decimal | None = None,
    amount_max: Decimal | None = None,
    duplicate_confidence: DuplicateConfidence | None = None,
    has_balance: bool | None = None,
    transaction_date_from: date | None = None,
    transaction_date_to: date | None = None,
    connection: duckdb.DuckDBPyConnection | None = None,
) -> int:
    """Count canonical transactions with the same filters used by the list endpoint."""

    if connection is None:
        with database_connection() as new_connection:
            return _count_canonical_transactions(
                new_connection,
                bank_name=bank_name,
                account_id=account_id,
                source_file_id=source_file_id,
                direction=direction,
                description_contains=description_contains,
                amount_min=amount_min,
                amount_max=amount_max,
                duplicate_confidence=duplicate_confidence,
                has_balance=has_balance,
                transaction_date_from=transaction_date_from,
                transaction_date_to=transaction_date_to,
            )

    return _count_canonical_transactions(
        connection,
        bank_name=bank_name,
        account_id=account_id,
        source_file_id=source_file_id,
        direction=direction,
        description_contains=description_contains,
        amount_min=amount_min,
        amount_max=amount_max,
        duplicate_confidence=duplicate_confidence,
        has_balance=has_balance,
        transaction_date_from=transaction_date_from,
        transaction_date_to=transaction_date_to,
    )


def summarize_canonical_transactions(
    *,
    group_by: TransactionSummaryGroupBy,
    bank_name: str | None = None,
    account_id: str | None = None,
    source_file_id: UUID | None = None,
    direction: TransactionDirection | None = None,
    description_contains: str | None = None,
    amount_min: Decimal | None = None,
    amount_max: Decimal | None = None,
    duplicate_confidence: DuplicateConfidence | None = None,
    has_balance: bool | None = None,
    transaction_date_from: date | None = None,
    transaction_date_to: date | None = None,
    limit: int = 100,
    offset: int = 0,
    connection: duckdb.DuckDBPyConnection | None = None,
) -> list[TransactionSummaryRecord]:
    """Return grouped canonical transaction summary metrics."""

    if connection is None:
        with database_connection() as new_connection:
            return _summarize_canonical_transactions(
                new_connection,
                group_by=group_by,
                bank_name=bank_name,
                account_id=account_id,
                source_file_id=source_file_id,
                direction=direction,
                description_contains=description_contains,
                amount_min=amount_min,
                amount_max=amount_max,
                duplicate_confidence=duplicate_confidence,
                has_balance=has_balance,
                transaction_date_from=transaction_date_from,
                transaction_date_to=transaction_date_to,
                limit=limit,
                offset=offset,
            )

    return _summarize_canonical_transactions(
        connection,
        group_by=group_by,
        bank_name=bank_name,
        account_id=account_id,
        source_file_id=source_file_id,
        direction=direction,
        description_contains=description_contains,
        amount_min=amount_min,
        amount_max=amount_max,
        duplicate_confidence=duplicate_confidence,
        has_balance=has_balance,
        transaction_date_from=transaction_date_from,
        transaction_date_to=transaction_date_to,
        limit=limit,
        offset=offset,
    )


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


def _list_canonical_transactions(
    connection: duckdb.DuckDBPyConnection,
    *,
    bank_name: str | None,
    account_id: str | None,
    source_file_id: UUID | None,
    direction: TransactionDirection | None,
    description_contains: str | None,
    amount_min: Decimal | None,
    amount_max: Decimal | None,
    duplicate_confidence: DuplicateConfidence | None,
    has_balance: bool | None,
    transaction_date_from: date | None,
    transaction_date_to: date | None,
    limit: int,
    offset: int,
) -> list[CanonicalTransactionViewRecord]:
    query = """
    SELECT
        ct.transaction_id,
        ct.source_file_id,
        ct.raw_row_id,
        ct.bank_name,
        ct.account_id,
        ct.transaction_date,
        ct.value_date,
        ct.description_raw,
        ct.amount,
        ct.direction,
        ct.balance,
        ct.currency,
        ct.source_row_number,
        ct.reference_number,
        ct.transaction_fingerprint,
        ct.duplicate_confidence,
        ct.created_at,
        sf.original_filename,
        sf.import_status,
        sf.statement_start_date,
        sf.statement_end_date
    FROM canonical_transactions ct
    LEFT JOIN source_files sf ON sf.file_id = ct.source_file_id
    """
    filters, parameters = _build_canonical_transaction_filters(
        bank_name=bank_name,
        account_id=account_id,
        source_file_id=source_file_id,
        direction=direction,
        description_contains=description_contains,
        amount_min=amount_min,
        amount_max=amount_max,
        duplicate_confidence=duplicate_confidence,
        has_balance=has_balance,
        transaction_date_from=transaction_date_from,
        transaction_date_to=transaction_date_to,
        table_alias="ct",
    )
    if filters:
        query += " WHERE " + " AND ".join(filters)

    query += """
    ORDER BY ct.transaction_date DESC, ct.created_at DESC, ct.transaction_id DESC
    LIMIT ? OFFSET ?
    """
    parameters.extend([limit, offset])
    rows = connection.execute(query, parameters).fetchall()
    return [_row_to_canonical_transaction_view_record(row) for row in rows]


def _count_canonical_transactions(
    connection: duckdb.DuckDBPyConnection,
    *,
    bank_name: str | None,
    account_id: str | None,
    source_file_id: UUID | None,
    direction: TransactionDirection | None,
    description_contains: str | None,
    amount_min: Decimal | None,
    amount_max: Decimal | None,
    duplicate_confidence: DuplicateConfidence | None,
    has_balance: bool | None,
    transaction_date_from: date | None,
    transaction_date_to: date | None,
) -> int:
    query = "SELECT COUNT(*) FROM canonical_transactions ct"
    filters, parameters = _build_canonical_transaction_filters(
        bank_name=bank_name,
        account_id=account_id,
        source_file_id=source_file_id,
        direction=direction,
        description_contains=description_contains,
        amount_min=amount_min,
        amount_max=amount_max,
        duplicate_confidence=duplicate_confidence,
        has_balance=has_balance,
        transaction_date_from=transaction_date_from,
        transaction_date_to=transaction_date_to,
        table_alias="ct",
    )
    if filters:
        query += " WHERE " + " AND ".join(filters)

    row = connection.execute(query, parameters).fetchone()
    if row is None:
        return 0

    return cast(int, row[0])


def _summarize_canonical_transactions(
    connection: duckdb.DuckDBPyConnection,
    *,
    group_by: TransactionSummaryGroupBy,
    bank_name: str | None,
    account_id: str | None,
    source_file_id: UUID | None,
    direction: TransactionDirection | None,
    description_contains: str | None,
    amount_min: Decimal | None,
    amount_max: Decimal | None,
    duplicate_confidence: DuplicateConfidence | None,
    has_balance: bool | None,
    transaction_date_from: date | None,
    transaction_date_to: date | None,
    limit: int,
    offset: int,
) -> list[TransactionSummaryRecord]:
    date_bucket_expression = _date_bucket_expression(group_by)
    query = f"""
    WITH filtered AS (
        SELECT
            ct.*,
            {date_bucket_expression} AS period_start
        FROM canonical_transactions ct
    """
    filters, parameters = _build_canonical_transaction_filters(
        bank_name=bank_name,
        account_id=account_id,
        source_file_id=source_file_id,
        direction=direction,
        description_contains=description_contains,
        amount_min=amount_min,
        amount_max=amount_max,
        duplicate_confidence=duplicate_confidence,
        has_balance=has_balance,
        transaction_date_from=transaction_date_from,
        transaction_date_to=transaction_date_to,
        table_alias="ct",
    )
    if filters:
        query += " WHERE " + " AND ".join(filters)

    query += """
    ),
    ranked AS (
        SELECT
            *,
            ROW_NUMBER() OVER (
                PARTITION BY period_start
                ORDER BY
                    CASE WHEN balance IS NULL THEN 1 ELSE 0 END,
                    transaction_date ASC,
                    source_row_number ASC,
                    created_at ASC,
                    transaction_id ASC
            ) AS opening_rank,
            ROW_NUMBER() OVER (
                PARTITION BY period_start
                ORDER BY
                    CASE WHEN balance IS NULL THEN 1 ELSE 0 END,
                    transaction_date DESC,
                    source_row_number DESC,
                    created_at DESC,
                    transaction_id DESC
            ) AS closing_rank
        FROM filtered
    )
    SELECT
        period_start,
        COUNT(*) AS transaction_count,
        COALESCE(SUM(CASE WHEN direction = 'DEBIT' THEN 1 ELSE 0 END), 0) AS debit_count,
        COALESCE(SUM(CASE WHEN direction = 'CREDIT' THEN 1 ELSE 0 END), 0) AS credit_count,
        COALESCE(SUM(CASE WHEN direction = 'DEBIT' THEN amount ELSE 0 END), 0) AS debit_total,
        COALESCE(SUM(CASE WHEN direction = 'CREDIT' THEN amount ELSE 0 END), 0) AS credit_total,
        COALESCE(SUM(CASE WHEN direction = 'CREDIT' THEN amount ELSE -amount END), 0) AS net_amount,
        MAX(CASE WHEN opening_rank = 1 THEN balance ELSE NULL END) AS opening_balance,
        MAX(CASE WHEN closing_rank = 1 THEN balance ELSE NULL END) AS closing_balance
    FROM ranked
    """
    query += """
    GROUP BY period_start
    ORDER BY period_start DESC
    LIMIT ? OFFSET ?
    """
    parameters.extend([limit, offset])
    rows = connection.execute(query, parameters).fetchall()
    return [
        TransactionSummaryRecord.model_validate(
            {
                "period_start": row[0],
                "group_by": group_by.value,
                "transaction_count": row[1],
                "debit_count": row[2],
                "credit_count": row[3],
                "debit_total": row[4],
                "credit_total": row[5],
                "net_amount": row[6],
                "opening_balance": row[7],
                "closing_balance": row[8],
            }
        )
        for row in rows
    ]


def _date_bucket_expression(group_by: TransactionSummaryGroupBy) -> str:
    if group_by == TransactionSummaryGroupBy.MONTH:
        return "CAST(date_trunc('month', ct.transaction_date) AS DATE)"

    group_by_value = group_by.value if hasattr(group_by, "value") else str(group_by)
    raise ValueError(f"Unsupported transaction summary grouping '{group_by_value}'.")


def _build_canonical_transaction_filters(
    *,
    bank_name: str | None,
    account_id: str | None,
    source_file_id: UUID | None,
    direction: TransactionDirection | None,
    description_contains: str | None,
    amount_min: Decimal | None,
    amount_max: Decimal | None,
    duplicate_confidence: DuplicateConfidence | None,
    has_balance: bool | None,
    transaction_date_from: date | None,
    transaction_date_to: date | None,
    table_alias: str | None = None,
) -> tuple[list[str], list[object]]:
    filters: list[str] = []
    parameters: list[object] = []
    prefix = f"{table_alias}." if table_alias else ""
    if bank_name is not None:
        filters.append(f"{prefix}bank_name = ?")
        parameters.append(bank_name)
    if account_id is not None:
        filters.append(f"COALESCE({prefix}account_id, '') = ?")
        parameters.append(account_id)
    if source_file_id is not None:
        filters.append(f"{prefix}source_file_id = ?")
        parameters.append(str(source_file_id))
    if direction is not None:
        filters.append(f"{prefix}direction = ?")
        parameters.append(direction.value)
    if description_contains is not None:
        search_term = f"%{description_contains.lower()}%"
        filters.append(
            f"(LOWER({prefix}description_raw) LIKE ? "
            f"OR LOWER(COALESCE({prefix}reference_number, '')) LIKE ?)"
        )
        parameters.extend([search_term, search_term])
    if amount_min is not None:
        filters.append(f"{prefix}amount >= ?")
        parameters.append(amount_min)
    if amount_max is not None:
        filters.append(f"{prefix}amount <= ?")
        parameters.append(amount_max)
    if duplicate_confidence is not None:
        filters.append(f"{prefix}duplicate_confidence = ?")
        parameters.append(duplicate_confidence.value)
    if has_balance is True:
        filters.append(f"{prefix}balance IS NOT NULL")
    elif has_balance is False:
        filters.append(f"{prefix}balance IS NULL")
    if transaction_date_from is not None:
        filters.append(f"{prefix}transaction_date >= ?")
        parameters.append(transaction_date_from)
    if transaction_date_to is not None:
        filters.append(f"{prefix}transaction_date <= ?")
        parameters.append(transaction_date_to)

    return filters, parameters


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


def _row_to_canonical_transaction_view_record(
    row: tuple[object, ...],
) -> CanonicalTransactionViewRecord:
    base_record = _row_to_canonical_transaction_record(row[:17])
    return CanonicalTransactionViewRecord.model_validate(
        {
            **base_record.model_dump(),
            "source_filename": cast(str | None, row[17]),
            "source_import_status": cast(str | None, row[18]),
            "source_statement_start_date": cast(date | None, row[19]),
            "source_statement_end_date": cast(date | None, row[20]),
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
