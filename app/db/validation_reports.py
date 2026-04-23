"""Repository helpers for validation report persistence."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import cast
from uuid import UUID

import duckdb

from app.db.database import database_connection
from app.models.validation import ValidationReportRecord

VALIDATION_REPORT_SELECT_SQL = """
SELECT
    report_id,
    file_id,
    total_rows,
    accepted_rows,
    ignored_rows,
    suspicious_rows,
    duplicate_rows,
    transactions_imported,
    reconciliation_status,
    ledger_continuity_status,
    final_status,
    issues,
    messages,
    generated_at
FROM validation_reports
WHERE file_id = ?
ORDER BY generated_at DESC
LIMIT 1
"""


def upsert_validation_report(
    report: ValidationReportRecord,
    *,
    connection: duckdb.DuckDBPyConnection | None = None,
) -> ValidationReportRecord:
    """Persist a validation report and return the latest report for its file."""

    if connection is None:
        with database_connection() as new_connection:
            return _upsert_validation_report(new_connection, report)

    return _upsert_validation_report(connection, report)


def get_validation_report_by_file_id(
    file_id: UUID,
    *,
    connection: duckdb.DuckDBPyConnection | None = None,
) -> ValidationReportRecord | None:
    """Fetch the latest validation report for a file."""

    if connection is None:
        with database_connection() as new_connection:
            return _fetch_validation_report_by_file_id(new_connection, file_id)

    return _fetch_validation_report_by_file_id(connection, file_id)


def _upsert_validation_report(
    connection: duckdb.DuckDBPyConnection,
    report: ValidationReportRecord,
) -> ValidationReportRecord:
    connection.execute(
        """
        INSERT INTO validation_reports (
            report_id,
            file_id,
            total_rows,
            accepted_rows,
            ignored_rows,
            suspicious_rows,
            duplicate_rows,
            transactions_imported,
            reconciliation_status,
            ledger_continuity_status,
            final_status,
            issues,
            messages,
            generated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            str(report.report_id),
            str(report.file_id),
            report.total_rows,
            report.accepted_rows,
            report.ignored_rows,
            report.suspicious_rows,
            report.duplicate_rows,
            report.transactions_imported,
            report.reconciliation_status.value,
            report.ledger_continuity_status.value,
            report.final_status,
            json.dumps([issue.model_dump(mode="json") for issue in report.issues]),
            json.dumps(report.messages),
            _as_utc_naive(report.generated_at),
        ],
    )
    persisted_report = _fetch_validation_report_by_file_id(connection, report.file_id)
    if persisted_report is None:
        raise LookupError(f"Validation report for '{report.file_id}' was not persisted.")

    return persisted_report


def _fetch_validation_report_by_file_id(
    connection: duckdb.DuckDBPyConnection,
    file_id: UUID,
) -> ValidationReportRecord | None:
    row = connection.execute(VALIDATION_REPORT_SELECT_SQL, [str(file_id)]).fetchone()
    if row is None:
        return None

    return ValidationReportRecord.model_validate(
        {
            "report_id": cast(str, row[0]),
            "file_id": cast(str, row[1]),
            "total_rows": cast(int, row[2]),
            "accepted_rows": cast(int, row[3]),
            "ignored_rows": cast(int, row[4]),
            "suspicious_rows": cast(int, row[5]),
            "duplicate_rows": cast(int, row[6]),
            "transactions_imported": cast(int, row[7]),
            "reconciliation_status": cast(str, row[8]),
            "ledger_continuity_status": cast(str, row[9]),
            "final_status": cast(str, row[10]),
            "issues": json.loads(cast(str, row[11])),
            "messages": json.loads(cast(str, row[12])),
            "generated_at": _with_utc_timezone(cast(datetime, row[13])),
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
