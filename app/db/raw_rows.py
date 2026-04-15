"""Repository helpers for raw-row audit records."""

from __future__ import annotations

import json
from collections.abc import Sequence
from typing import cast
from uuid import UUID

import duckdb

from app.db.database import database_connection
from app.models.parsing import RawRowAuditSummary, RawRowRecord

RAW_ROWS_BY_FILE_SELECT_SQL = """
SELECT
    raw_row_id,
    file_id,
    row_number,
    parser_name,
    parser_version,
    row_type,
    raw_text,
    normalized_text,
    raw_payload,
    rejection_reason,
    header_row,
    repaired_row
FROM raw_rows
WHERE file_id = ?
ORDER BY row_number
"""

RAW_ROW_AUDIT_SUMMARY_SQL = """
SELECT
    COUNT(*) AS raw_rows_recorded,
    COALESCE(
        SUM(CASE WHEN row_type = 'accepted' THEN 1 ELSE 0 END),
        0
    ) AS accepted_rows_recorded,
    COALESCE(SUM(CASE WHEN row_type = 'ignored' THEN 1 ELSE 0 END), 0) AS ignored_rows_recorded,
    COALESCE(
        SUM(CASE WHEN row_type = 'suspicious' THEN 1 ELSE 0 END),
        0
    ) AS suspicious_rows_recorded,
    COALESCE(MAX(CASE WHEN header_row THEN 1 ELSE 0 END), 0) AS header_detected
FROM raw_rows
WHERE file_id = ?
"""


def insert_raw_rows(
    records: Sequence[RawRowRecord],
    *,
    connection: duckdb.DuckDBPyConnection | None = None,
) -> None:
    """Persist a batch of raw-row audit records."""

    if not records:
        return

    if connection is None:
        with database_connection() as new_connection:
            _insert_raw_rows(new_connection, records)
        return

    _insert_raw_rows(connection, records)


def get_raw_row_audit_summary(
    file_id: UUID,
    *,
    connection: duckdb.DuckDBPyConnection | None = None,
) -> RawRowAuditSummary:
    """Return aggregate inspection counts for a source file."""

    if connection is None:
        with database_connection() as new_connection:
            return _fetch_raw_row_audit_summary(new_connection, file_id)

    return _fetch_raw_row_audit_summary(connection, file_id)


def get_raw_rows_by_file_id(
    file_id: UUID,
    *,
    connection: duckdb.DuckDBPyConnection | None = None,
) -> list[RawRowRecord]:
    """Return persisted raw-row audit records for a source file."""

    if connection is None:
        with database_connection() as new_connection:
            return _fetch_raw_rows_by_file_id(new_connection, file_id)

    return _fetch_raw_rows_by_file_id(connection, file_id)


def _insert_raw_rows(
    connection: duckdb.DuckDBPyConnection,
    records: Sequence[RawRowRecord],
) -> None:
    connection.executemany(
        """
        INSERT INTO raw_rows (
            raw_row_id,
            file_id,
            row_number,
            parser_name,
            parser_version,
            row_type,
            raw_text,
            normalized_text,
            raw_payload,
            rejection_reason,
            header_row,
            repaired_row
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            [
                str(record.raw_row_id),
                str(record.file_id),
                record.row_number,
                record.parser_name,
                record.parser_version,
                record.row_type.value,
                record.raw_text,
                record.normalized_text,
                json.dumps(record.raw_payload) if record.raw_payload is not None else None,
                record.rejection_reason,
                record.header_row,
                record.repaired_row,
            ]
            for record in records
        ],
    )


def _fetch_raw_row_audit_summary(
    connection: duckdb.DuckDBPyConnection,
    file_id: UUID,
) -> RawRowAuditSummary:
    row = connection.execute(RAW_ROW_AUDIT_SUMMARY_SQL, [str(file_id)]).fetchone()
    if row is None:
        return RawRowAuditSummary()

    return RawRowAuditSummary.model_validate(
        {
            "raw_rows_recorded": cast(int, row[0]),
            "accepted_rows_recorded": cast(int, row[1]),
            "ignored_rows_recorded": cast(int, row[2]),
            "suspicious_rows_recorded": cast(int, row[3]),
            "header_detected": bool(cast(int, row[4])),
        }
    )


def _fetch_raw_rows_by_file_id(
    connection: duckdb.DuckDBPyConnection,
    file_id: UUID,
) -> list[RawRowRecord]:
    rows = connection.execute(RAW_ROWS_BY_FILE_SELECT_SQL, [str(file_id)]).fetchall()
    return [_row_to_raw_row_record(row) for row in rows]


def _row_to_raw_row_record(row: tuple[object, ...]) -> RawRowRecord:
    raw_payload = cast(str | None, row[8])
    return RawRowRecord.model_validate(
        {
            "raw_row_id": cast(str, row[0]),
            "file_id": cast(str, row[1]),
            "row_number": cast(int, row[2]),
            "parser_name": cast(str, row[3]),
            "parser_version": cast(str, row[4]),
            "row_type": cast(str, row[5]),
            "raw_text": cast(str, row[6]),
            "normalized_text": cast(str | None, row[7]),
            "raw_payload": json.loads(raw_payload) if raw_payload is not None else None,
            "rejection_reason": cast(str | None, row[9]),
            "header_row": cast(bool, row[10]),
            "repaired_row": cast(bool, row[11]),
        }
    )
