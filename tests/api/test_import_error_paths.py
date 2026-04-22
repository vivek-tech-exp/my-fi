"""API tests for import error paths."""

import asyncio
from io import BytesIO
from uuid import uuid4

import pytest
from app.api.routes import imports as imports_route
from app.api.routes.imports import _process_batch_file, _stage_upload, upload_csv, upload_csv_batch
from app.core.config import get_settings
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


def test_stage_upload_rejects_files_over_configured_size_limit(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    del client
    monkeypatch.setenv("MY_FI_MAX_UPLOAD_FILE_SIZE_BYTES", "4")
    get_settings.cache_clear()
    upload_file = UploadFile(
        filename="too-large.csv",
        file=BytesIO(b"12345"),
    )

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(_stage_upload(upload_file))

    get_settings.cache_clear()
    assert exc_info.value.status_code == 413
    assert "exceeds the configured 4 byte limit" in str(exc_info.value.detail)


def test_batch_upload_rejects_empty_file_list(client: TestClient) -> None:
    del client

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(upload_csv_batch([], BankName.KOTAK))

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "At least one CSV file must be uploaded."


def test_batch_upload_returns_file_error_when_processing_fails(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    del client

    def fail_processing(*_args, **_kwargs):
        raise RuntimeError("database unavailable")

    monkeypatch.setattr(imports_route, "store_uploaded_csv_from_path", fail_processing)
    upload_file = UploadFile(
        filename="statement.csv",
        file=BytesIO(b"Date,Narration\n2026-04-01,Cafe\n"),
    )

    response = asyncio.run(_process_batch_file(upload_file=upload_file, bank_name=BankName.HDFC))

    assert response.original_filename == "statement.csv"
    assert response.status_code == 500
    assert response.result is None
    assert response.error == "File import failed. Review import logs for diagnostics."


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
