"""Routes for source file imports."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, File, Form, HTTPException, Response, UploadFile, status

from app.db.raw_rows import get_raw_rows_by_file_id
from app.db.source_files import get_source_file_by_id, list_source_files
from app.db.validation_reports import get_validation_report_by_file_id
from app.models.imports import (
    BankName,
    ImportDetailResponse,
    ImportSummaryResponse,
    SourceFileRecord,
    UploadCsvResponse,
)
from app.models.parsing import RawRowRecord
from app.models.validation import ValidationReportRecord
from app.services.imports import store_uploaded_csv

router = APIRouter(prefix="/imports", tags=["imports"])


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
    account_id: Annotated[str | None, Form(description="Optional account identifier")] = None,
) -> UploadCsvResponse:
    try:
        if not file.filename:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Uploaded file must include a filename.",
            )

        file_bytes = await file.read()
    finally:
        await file.close()

    if not file_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty.",
        )

    normalized_account_id = account_id.strip() or None if account_id else None

    upload_response = store_uploaded_csv(
        file_bytes=file_bytes,
        original_filename=file.filename,
        bank_name=bank_name,
        account_id=normalized_account_id,
    )
    response.status_code = (
        status.HTTP_200_OK if upload_response.duplicate_file else status.HTTP_201_CREATED
    )
    return upload_response


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


def _get_source_file_or_404(file_id: UUID) -> SourceFileRecord:
    try:
        return get_source_file_by_id(file_id)
    except LookupError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
