"""DuckDB connection and schema bootstrap."""

from collections.abc import Iterator
from contextlib import contextmanager

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


@contextmanager
def database_connection() -> Iterator[duckdb.DuckDBPyConnection]:
    """Yield a connection to the configured DuckDB database."""

    settings = get_settings()
    connection = duckdb.connect(str(settings.database_path))
    try:
        yield connection
    finally:
        connection.close()


def initialize_database() -> None:
    """Create the required database schema for the current milestone."""

    with database_connection() as connection:
        connection.execute(SOURCE_FILES_TABLE_SQL)
