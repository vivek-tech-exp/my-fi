"""API tests for import error paths."""

import asyncio
from io import BytesIO
from uuid import uuid4

import pytest
from app.api.routes.imports import upload_csv
from app.db.source_files import insert_source_file
from app.models.imports import BankName
from fastapi import HTTPException, Response, UploadFile
from fastapi.testclient import TestClient
from tests.factories import source_file_record


def test_upload_csv_rejects_missing_filename(client: TestClient) -> None:
    del client
    upload_file = UploadFile(
        filename="",
        file=BytesIO(b"Date,Narration\n"),
    )

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(upload_csv(Response(), upload_file, BankName.KOTAK))

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "Uploaded file must include a filename."


def test_import_lookup_endpoints_return_404_for_unknown_file(client: TestClient) -> None:
    file_id = uuid4()

    assert client.get(f"/imports/{file_id}").status_code == 404
    assert client.get(f"/imports/{file_id}/report").status_code == 404
    assert client.get(f"/imports/{file_id}/rows").status_code == 404
    assert client.post(f"/imports/{file_id}/reprocess").status_code == 404


def test_report_endpoint_returns_404_when_report_is_missing(client: TestClient) -> None:
    record = insert_source_file(
        source_file_record(
            bank_name=BankName.KOTAK,
            file_hash="b" * 64,
        )
    )

    response = client.get(f"/imports/{record.file_id}/report")

    assert response.status_code == 404
    assert response.json() == {"detail": "Validation report was not found for this import."}


def test_reprocess_returns_409_when_stored_file_is_missing(client: TestClient) -> None:
    record = insert_source_file(
        source_file_record(
            bank_name=BankName.KOTAK,
            file_hash="c" * 64,
            stored_path="/tmp/does-not-exist-for-my-fi-tests.csv",
        )
    )

    response = client.post(f"/imports/{record.file_id}/reprocess")

    assert response.status_code == 409
    assert "Stored source file" in response.json()["detail"]
