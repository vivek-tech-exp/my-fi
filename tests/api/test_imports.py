"""Tests for the CSV upload endpoint."""

from hashlib import sha256
from pathlib import Path

from fastapi.testclient import TestClient


def test_upload_csv_persists_file_and_returns_metadata(client: TestClient) -> None:
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
    assert payload["file_size_bytes"] == len(file_bytes)
    assert payload["status"] == "RECEIVED"
    assert payload["message"].startswith("File stored locally.")
    assert stored_path.exists()
    assert stored_path.read_bytes() == file_bytes
    assert "hdfc" in stored_path.parts
    assert stored_path.name.startswith(payload["file_hash"])


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
