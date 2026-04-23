"""DuckDB connection and schema bootstrap."""

from collections.abc import Iterator
from contextlib import contextmanager
from threading import RLock

import duckdb

from app.core.config import get_settings

SOURCE_FILES_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS source_files (
    file_id VARCHAR PRIMARY KEY,
    original_filename VARCHAR NOT NULL,
    stored_path VARCHAR NOT NULL,
    bank_name VARCHAR NOT NULL,
    account_id VARCHAR,
    file_hash VARCHAR NOT NULL,
    file_size_bytes BIGINT NOT NULL,
    uploaded_at TIMESTAMP NOT NULL,
    parser_version VARCHAR NOT NULL,
    import_status VARCHAR NOT NULL,
    statement_start_date DATE,
    statement_end_date DATE,
    encoding_detected VARCHAR,
    delimiter_detected VARCHAR
);
"""

SOURCE_FILES_FILE_HASH_INDEX_SQL = """
CREATE UNIQUE INDEX IF NOT EXISTS source_files_file_hash_idx
ON source_files(file_hash);
"""

RAW_ROWS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS raw_rows (
    raw_row_id VARCHAR PRIMARY KEY,
    file_id VARCHAR NOT NULL,
    row_number INTEGER NOT NULL,
    parser_name VARCHAR NOT NULL,
    parser_version VARCHAR NOT NULL,
    row_type VARCHAR NOT NULL,
    raw_text VARCHAR NOT NULL,
    normalized_text VARCHAR,
    raw_payload VARCHAR,
    rejection_reason VARCHAR,
    header_row BOOLEAN NOT NULL DEFAULT FALSE,
    repaired_row BOOLEAN NOT NULL DEFAULT FALSE
);
"""

RAW_ROWS_FILE_ID_INDEX_SQL = """
CREATE INDEX IF NOT EXISTS raw_rows_file_id_idx
ON raw_rows(file_id, row_number);
"""

CANONICAL_TRANSACTIONS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS canonical_transactions (
    transaction_id VARCHAR PRIMARY KEY,
    source_file_id VARCHAR NOT NULL,
    raw_row_id VARCHAR NOT NULL,
    bank_name VARCHAR NOT NULL,
    account_id VARCHAR,
    transaction_date DATE NOT NULL,
    value_date DATE,
    description_raw VARCHAR NOT NULL,
    amount DECIMAL(18, 2) NOT NULL,
    direction VARCHAR NOT NULL,
    balance DECIMAL(18, 2),
    currency VARCHAR NOT NULL,
    source_row_number INTEGER NOT NULL,
    reference_number VARCHAR,
    transaction_fingerprint VARCHAR NOT NULL,
    duplicate_confidence VARCHAR NOT NULL,
    created_at TIMESTAMP NOT NULL
);
"""

CANONICAL_TRANSACTIONS_FILE_ID_INDEX_SQL = """
CREATE INDEX IF NOT EXISTS canonical_transactions_file_id_idx
ON canonical_transactions(source_file_id, source_row_number);
"""

VALIDATION_REPORTS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS validation_reports (
    report_id VARCHAR PRIMARY KEY,
    file_id VARCHAR NOT NULL,
    total_rows INTEGER NOT NULL,
    accepted_rows INTEGER NOT NULL,
    ignored_rows INTEGER NOT NULL,
    suspicious_rows INTEGER NOT NULL,
    duplicate_rows INTEGER NOT NULL,
    transactions_imported INTEGER NOT NULL,
    reconciliation_status VARCHAR NOT NULL,
    ledger_continuity_status VARCHAR NOT NULL,
    final_status VARCHAR NOT NULL,
    messages VARCHAR NOT NULL,
    generated_at TIMESTAMP NOT NULL
);
"""

VALIDATION_REPORTS_FILE_ID_INDEX_SQL = """
CREATE INDEX IF NOT EXISTS validation_reports_file_id_idx
ON validation_reports(file_id, generated_at);
"""

_DATABASE_LOCK = RLock()


@contextmanager
def database_connection() -> Iterator[duckdb.DuckDBPyConnection]:
    """Yield a connection to the configured DuckDB database."""

    settings = get_settings()
    with _DATABASE_LOCK:
        connection = duckdb.connect(str(settings.database_path))
        try:
            yield connection
        finally:
            connection.close()


def initialize_database() -> None:
    """Create the required database schema for the current milestone."""

    with database_connection() as connection:
        connection.execute(SOURCE_FILES_TABLE_SQL)
        connection.execute(SOURCE_FILES_FILE_HASH_INDEX_SQL)
        connection.execute(RAW_ROWS_TABLE_SQL)
        connection.execute(RAW_ROWS_FILE_ID_INDEX_SQL)
        connection.execute(CANONICAL_TRANSACTIONS_TABLE_SQL)
        connection.execute(CANONICAL_TRANSACTIONS_FILE_ID_INDEX_SQL)
        connection.execute(VALIDATION_REPORTS_TABLE_SQL)
        connection.execute(VALIDATION_REPORTS_FILE_ID_INDEX_SQL)
