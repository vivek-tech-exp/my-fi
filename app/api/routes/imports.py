"""Routes for source file imports."""

from dataclasses import dataclass
from hashlib import sha256
from os import fsync
from pathlib import Path
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, File, Form, HTTPException, Response, UploadFile, status
from starlette.concurrency import run_in_threadpool

from app.core.config import get_settings
from app.core.logging import get_import_logger
from app.db.raw_rows import get_raw_rows_by_file_id
from app.db.source_files import get_source_file_by_id, list_source_files
from app.db.validation_reports import get_validation_report_by_file_id
from app.models.imports import (
    BankName,
    ImportDetailResponse,
    ImportSummaryResponse,
    SourceFileRecord,
    UploadCsvBatchItemResponse,
    UploadCsvBatchResponse,
    UploadCsvResponse,
)
from app.models.parsing import RawRowRecord
from app.models.validation import ValidationReportRecord
from app.services.imports import reprocess_import, store_uploaded_csv_from_path

router = APIRouter(prefix="/imports", tags=["imports"])


@dataclass(frozen=True)
class StagedUpload:
    """Temporary on-disk upload ready for import processing."""

    original_filename: str
    source_path: Path
    file_hash: str
    file_size_bytes: int


@router.post(
    "/csv",
    response_model=UploadCsvResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a bank CSV file",
)
async def upload_csv(
    response: Response,
    file: Annotated[UploadFile, File(description="CSV file to ingest")],
    bank_name: Annotated[BankName, Form(description="Bank that produced the export")],
) -> UploadCsvResponse:
    staged_upload = await _stage_upload(file)
    upload_response = await run_in_threadpool(
        store_uploaded_csv_from_path,
        source_path=staged_upload.source_path,
        original_filename=staged_upload.original_filename,
        bank_name=bank_name,
        file_hash=staged_upload.file_hash,
        file_size_bytes=staged_upload.file_size_bytes,
    )
    response.status_code = (
        status.HTTP_200_OK if upload_response.duplicate_file else status.HTTP_201_CREATED
    )
    return upload_response


@router.post(
    "/csv/batch",
    response_model=UploadCsvBatchResponse,
    summary="Upload multiple bank CSV files",
)
async def upload_csv_batch(
    files: Annotated[list[UploadFile], File(description="CSV files to ingest")],
    bank_name: Annotated[BankName, Form(description="Bank that produced the exports")],
) -> UploadCsvBatchResponse:
    if not files:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one CSV file must be uploaded.",
        )

    results: list[UploadCsvBatchItemResponse] = []
    for upload_file in files:
        results.append(await _process_batch_file(upload_file=upload_file, bank_name=bank_name))

    return UploadCsvBatchResponse(
        total_files=len(results),
        succeeded=sum(1 for result in results if result.result is not None),
        failed=sum(1 for result in results if result.error is not None),
        duplicates=sum(
            1 for result in results if result.result is not None and result.result.duplicate_file
        ),
        results=results,
    )


@router.get(
    "",
    response_model=list[ImportSummaryResponse],
    summary="List import metadata",
)
def list_imports() -> list[ImportSummaryResponse]:
    return [ImportSummaryResponse.from_source_file_record(record) for record in list_source_files()]


@router.get(
    "/{file_id}",
    response_model=ImportDetailResponse,
    summary="Get import metadata",
)
def get_import(file_id: UUID) -> ImportDetailResponse:
    record = _get_source_file_or_404(file_id)
    return ImportDetailResponse.from_source_file_record(
        record,
        report=get_validation_report_by_file_id(file_id),
    )


@router.get(
    "/{file_id}/report",
    response_model=ValidationReportRecord,
    summary="Get import validation report",
)
def get_import_report(file_id: UUID) -> ValidationReportRecord:
    _get_source_file_or_404(file_id)
    report = get_validation_report_by_file_id(file_id)
    if report is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Validation report was not found for this import.",
        )

    return report


@router.get(
    "/{file_id}/rows",
    response_model=list[RawRowRecord],
    summary="Get raw-row audit trail",
)
def get_import_rows(file_id: UUID) -> list[RawRowRecord]:
    _get_source_file_or_404(file_id)
    return get_raw_rows_by_file_id(file_id)


@router.post(
    "/{file_id}/reprocess",
    response_model=UploadCsvResponse,
    summary="Reprocess a stored import",
)
def reprocess_import_route(file_id: UUID) -> UploadCsvResponse:
    try:
        return reprocess_import(file_id)
    except LookupError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc


def _get_source_file_or_404(file_id: UUID) -> SourceFileRecord:
    try:
        return get_source_file_by_id(file_id)
    except LookupError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


async def _process_batch_file(
    *,
    upload_file: UploadFile,
    bank_name: BankName,
) -> UploadCsvBatchItemResponse:
    filename = upload_file.filename or "<missing filename>"
    try:
        staged_upload = await _stage_upload(upload_file)
        result = await run_in_threadpool(
            store_uploaded_csv_from_path,
            source_path=staged_upload.source_path,
            original_filename=staged_upload.original_filename,
            bank_name=bank_name,
            file_hash=staged_upload.file_hash,
            file_size_bytes=staged_upload.file_size_bytes,
        )
    except HTTPException as exc:
        _log_batch_upload_failure(filename=filename, status_code=exc.status_code, error=exc.detail)
        return UploadCsvBatchItemResponse(
            original_filename=filename,
            status_code=exc.status_code,
            error=str(exc.detail),
        )
    except Exception as exc:
        _log_batch_upload_failure(
            filename=filename,
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            error=str(exc),
        )
        return UploadCsvBatchItemResponse(
            original_filename=filename,
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            error="File import failed. Review import logs for diagnostics.",
        )

    return UploadCsvBatchItemResponse(
        original_filename=staged_upload.original_filename,
        status_code=status.HTTP_200_OK if result.duplicate_file else status.HTTP_201_CREATED,
        result=result,
    )


async def _stage_upload(upload_file: UploadFile) -> StagedUpload:
    settings = get_settings()
    settings.upload_staging_dir.mkdir(parents=True, exist_ok=True)

    if not upload_file.filename:
        await upload_file.close()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file must include a filename.",
        )

    staging_path = settings.upload_staging_dir / f"{uuid4()}.upload"
    file_hash = sha256()
    file_size_bytes = 0

    try:
        with staging_path.open("wb") as staged_file:
            while chunk := await upload_file.read(settings.upload_chunk_size_bytes):
                file_size_bytes += len(chunk)
                if file_size_bytes > settings.max_upload_file_size_bytes:
                    raise HTTPException(
                        status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                        detail=(
                            "Uploaded file exceeds the configured "
                            f"{settings.max_upload_file_size_bytes} byte limit."
                        ),
                    )

                file_hash.update(chunk)
                staged_file.write(chunk)

            staged_file.flush()
            fsync(staged_file.fileno())
    except Exception:
        staging_path.unlink(missing_ok=True)
        raise
    finally:
        await upload_file.close()

    if file_size_bytes == 0:
        staging_path.unlink(missing_ok=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty.",
        )

    return StagedUpload(
        original_filename=upload_file.filename,
        source_path=staging_path,
        file_hash=file_hash.hexdigest(),
        file_size_bytes=file_size_bytes,
    )


def _log_batch_upload_failure(*, filename: str, status_code: int, error: object) -> None:
    get_import_logger().error(
        "batch_upload_file_failed filename=%r status_code=%s error=%r",
        filename,
        status_code,
        error,
    )
