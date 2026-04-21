"""Repository helpers for the source file registry."""

from datetime import UTC, date, datetime
from typing import cast
from uuid import UUID

import duckdb

from app.db.database import database_connection
from app.models.imports import ImportStatus, SourceFileRecord

SOURCE_FILE_SELECT_SQL = """
SELECT
    file_id,
    original_filename,
    stored_path,
    bank_name,
    account_id,
    file_hash,
    file_size_bytes,
    uploaded_at,
    parser_version,
    import_status,
    statement_start_date,
    statement_end_date,
    encoding_detected,
    delimiter_detected
FROM source_files
WHERE file_id = ?
"""

SOURCE_FILE_BY_HASH_SELECT_SQL = """
SELECT
    file_id,
    original_filename,
    stored_path,
    bank_name,
    account_id,
    file_hash,
    file_size_bytes,
    uploaded_at,
    parser_version,
    import_status,
    statement_start_date,
    statement_end_date,
    encoding_detected,
    delimiter_detected
FROM source_files
WHERE file_hash = ?
"""


def insert_source_file(
    record: SourceFileRecord,
    *,
    connection: duckdb.DuckDBPyConnection | None = None,
) -> SourceFileRecord:
    """Insert a source file row and return the persisted record."""

    if connection is None:
        with database_connection() as new_connection:
            return _insert_source_file(new_connection, record)

    return _insert_source_file(connection, record)


def get_source_file_by_id(
    file_id: UUID,
    *,
    connection: duckdb.DuckDBPyConnection | None = None,
) -> SourceFileRecord:
    """Fetch a source file registry row by file ID."""

    if connection is None:
        with database_connection() as new_connection:
            return _fetch_source_file(new_connection, file_id)

    return _fetch_source_file(connection, file_id)


def get_source_file_by_hash(
    file_hash: str,
    *,
    connection: duckdb.DuckDBPyConnection | None = None,
) -> SourceFileRecord | None:
    """Fetch a source file registry row by file hash, if it exists."""

    if connection is None:
        with database_connection() as new_connection:
            return _fetch_source_file_by_hash(new_connection, file_hash)

    return _fetch_source_file_by_hash(connection, file_hash)


def update_source_file_processing_result(
    *,
    file_id: UUID,
    import_status: ImportStatus,
    statement_start_date: date | None,
    statement_end_date: date | None,
    connection: duckdb.DuckDBPyConnection | None = None,
) -> SourceFileRecord:
    """Update the final parser outcome fields for a source file."""

    if connection is None:
        with database_connection() as new_connection:
            return _update_source_file_processing_result(
                new_connection,
                file_id=file_id,
                import_status=import_status,
                statement_start_date=statement_start_date,
                statement_end_date=statement_end_date,
            )

    return _update_source_file_processing_result(
        connection,
        file_id=file_id,
        import_status=import_status,
        statement_start_date=statement_start_date,
        statement_end_date=statement_end_date,
    )


def _insert_source_file(
    connection: duckdb.DuckDBPyConnection,
    record: SourceFileRecord,
) -> SourceFileRecord:
    connection.execute(
        """
        INSERT INTO source_files (
            file_id,
            original_filename,
            stored_path,
            bank_name,
            account_id,
            file_hash,
            file_size_bytes,
            uploaded_at,
            parser_version,
            import_status,
            statement_start_date,
            statement_end_date,
            encoding_detected,
            delimiter_detected
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            str(record.file_id),
            record.original_filename,
            record.stored_path,
            record.bank_name.value,
            record.account_id,
            record.file_hash,
            record.file_size_bytes,
            _as_utc_naive(record.uploaded_at),
            record.parser_version,
            record.import_status.value,
            record.statement_start_date,
            record.statement_end_date,
            record.encoding_detected,
            record.delimiter_detected,
        ],
    )
    return get_source_file_by_id(record.file_id, connection=connection)


def _update_source_file_processing_result(
    connection: duckdb.DuckDBPyConnection,
    *,
    file_id: UUID,
    import_status: ImportStatus,
    statement_start_date: date | None,
    statement_end_date: date | None,
) -> SourceFileRecord:
    connection.execute(
        """
        UPDATE source_files
        SET
            import_status = ?,
            statement_start_date = ?,
            statement_end_date = ?
        WHERE file_id = ?
        """,
        [
            import_status.value,
            statement_start_date,
            statement_end_date,
            str(file_id),
        ],
    )
    return get_source_file_by_id(file_id, connection=connection)


def _fetch_source_file(connection: duckdb.DuckDBPyConnection, file_id: UUID) -> SourceFileRecord:
    row = connection.execute(SOURCE_FILE_SELECT_SQL, [str(file_id)]).fetchone()
    if row is None:
        raise LookupError(f"Source file '{file_id}' was not found.")

    return _row_to_source_file_record(row)


def _fetch_source_file_by_hash(
    connection: duckdb.DuckDBPyConnection,
    file_hash: str,
) -> SourceFileRecord | None:
    row = connection.execute(SOURCE_FILE_BY_HASH_SELECT_SQL, [file_hash]).fetchone()
    if row is None:
        return None

    return _row_to_source_file_record(row)


def _row_to_source_file_record(row: tuple[object, ...]) -> SourceFileRecord:
    return SourceFileRecord.model_validate(
        {
            "file_id": cast(str, row[0]),
            "original_filename": cast(str, row[1]),
            "stored_path": cast(str, row[2]),
            "bank_name": cast(str, row[3]),
            "account_id": cast(str | None, row[4]),
            "file_hash": cast(str, row[5]),
            "file_size_bytes": cast(int, row[6]),
            "uploaded_at": _with_utc_timezone(cast(datetime, row[7])),
            "parser_version": cast(str, row[8]),
            "import_status": cast(str, row[9]),
            "statement_start_date": cast(date | None, row[10]),
            "statement_end_date": cast(date | None, row[11]),
            "encoding_detected": cast(str | None, row[12]),
            "delimiter_detected": cast(str | None, row[13]),
        }
    )


def _as_utc_naive(value: datetime) -> datetime:
    """Store datetimes in UTC without timezone metadata for DuckDB compatibility."""

    if value.tzinfo is None:
        return value

    return value.astimezone(UTC).replace(tzinfo=None)


def _with_utc_timezone(value: datetime) -> datetime:
    """Restore UTC timezone metadata for API responses."""

    if value.tzinfo is not None:
        return value.astimezone(UTC)

    return value.replace(tzinfo=UTC)
