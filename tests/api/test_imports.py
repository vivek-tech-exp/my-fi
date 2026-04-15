"""Tests for the CSV upload endpoint."""

from hashlib import sha256
from pathlib import Path

import duckdb
from app.core.config import Settings
from fastapi.testclient import TestClient


def test_upload_csv_persists_file_and_returns_metadata(
    client: TestClient,
    settings: Settings,
) -> None:
    file_bytes = b"Date,Narration,Debit,Credit,Balance\n2026-04-01,Salary,,1000.00,1000.00\n"

    response = client.post(
        "/imports/csv",
        data={"bank_name": "hdfc", "account_id": "primary-checking"},
        files={"file": ("salary_statement.csv", file_bytes, "text/csv")},
    )

    assert response.status_code == 201
    payload = response.json()
    stored_path = Path(payload["stored_path"])

    assert payload["bank_name"] == "hdfc"
    assert payload["account_id"] == "primary-checking"
    assert payload["original_filename"] == "salary_statement.csv"
    assert payload["file_hash"] == sha256(file_bytes).hexdigest()
    assert payload["duplicate_file"] is False
    assert payload["file_size_bytes"] == len(file_bytes)
    assert payload["parser_version"] == settings.default_parser_version
    assert payload["status"] == "RECEIVED"
    assert payload["message"].startswith("File stored locally and registered")
    assert stored_path.exists()
    assert stored_path.read_bytes() == file_bytes
    assert "hdfc" in stored_path.parts
    assert stored_path.name.startswith(payload["file_hash"])

    with duckdb.connect(str(settings.database_path), read_only=True) as connection:
        row = connection.execute(
            """
            SELECT
                bank_name,
                account_id,
                original_filename,
                stored_path,
                file_hash,
                file_size_bytes,
                parser_version,
                import_status,
                statement_start_date,
                statement_end_date,
                encoding_detected,
                delimiter_detected
            FROM source_files
            WHERE file_id = ?
            """,
            [payload["file_id"]],
        ).fetchone()

    assert row is not None
    assert row[0] == "hdfc"
    assert row[1] == "primary-checking"
    assert row[2] == "salary_statement.csv"
    assert row[3] == payload["stored_path"]
    assert row[4] == payload["file_hash"]
    assert row[5] == len(file_bytes)
    assert row[6] == settings.default_parser_version
    assert row[7] == "RECEIVED"
    assert row[8] is None
    assert row[9] is None
    assert row[10] is None
    assert row[11] is None


def test_upload_csv_rejects_empty_files(client: TestClient) -> None:
    response = client.post(
        "/imports/csv",
        data={"bank_name": "kotak"},
        files={"file": ("empty.csv", b"", "text/csv")},
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "Uploaded file is empty."}


def test_upload_csv_rejects_unknown_bank_name(client: TestClient) -> None:
    response = client.post(
        "/imports/csv",
        data={"bank_name": "unknown-bank"},
        files={"file": ("statement.csv", b"header\nrow\n", "text/csv")},
    )

    assert response.status_code == 422


def test_upload_csv_creates_database_file(client: TestClient, settings: Settings) -> None:
    response = client.post(
        "/imports/csv",
        data={"bank_name": "federal"},
        files={"file": ("statement.csv", b"header\nrow\n", "text/csv")},
    )

    assert response.status_code == 201
    assert settings.database_path.exists()


def test_upload_csv_returns_existing_record_for_duplicate_file(
    client: TestClient,
    settings: Settings,
) -> None:
    file_bytes = b"Date,Narration,Debit,Credit,Balance\n2026-04-01,Salary,,1000.00,1000.00\n"

    first_response = client.post(
        "/imports/csv",
        data={"bank_name": "hdfc", "account_id": "primary-checking"},
        files={"file": ("salary_statement.csv", file_bytes, "text/csv")},
    )
    second_response = client.post(
        "/imports/csv",
        data={"bank_name": "hdfc", "account_id": "secondary-account"},
        files={"file": ("renamed_statement.csv", file_bytes, "text/csv")},
    )

    assert first_response.status_code == 201
    assert second_response.status_code == 200

    first_payload = first_response.json()
    second_payload = second_response.json()

    assert second_payload["duplicate_file"] is True
    assert second_payload["file_id"] == first_payload["file_id"]
    assert second_payload["file_hash"] == first_payload["file_hash"]
    assert second_payload["stored_path"] == first_payload["stored_path"]
    assert second_payload["account_id"] == "primary-checking"
    assert second_payload["message"].startswith("Matching file already registered.")

    with duckdb.connect(str(settings.database_path), read_only=True) as connection:
        row_count = connection.execute("SELECT COUNT(*) FROM source_files").fetchone()

    assert row_count is not None
    assert row_count[0] == 1
