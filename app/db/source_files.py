"""Repository helpers for the source file registry."""

from datetime import UTC, datetime
from uuid import UUID

import duckdb

from app.db.database import database_connection
from app.models.imports import SourceFileRecord

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


def insert_source_file(record: SourceFileRecord) -> SourceFileRecord:
    """Insert a source file row and return the persisted record."""

    with database_connection() as connection:
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


def _fetch_source_file(connection: duckdb.DuckDBPyConnection, file_id: UUID) -> SourceFileRecord:
    row = connection.execute(SOURCE_FILE_SELECT_SQL, [str(file_id)]).fetchone()
    if row is None:
        raise LookupError(f"Source file '{file_id}' was not found.")

    return SourceFileRecord(
        file_id=row[0],
        original_filename=row[1],
        stored_path=row[2],
        bank_name=row[3],
        account_id=row[4],
        file_hash=row[5],
        file_size_bytes=row[6],
        uploaded_at=_with_utc_timezone(row[7]),
        parser_version=row[8],
        import_status=row[9],
        statement_start_date=row[10],
        statement_end_date=row[11],
        encoding_detected=row[12],
        delimiter_detected=row[13],
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
