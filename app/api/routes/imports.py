"""Routes for source file imports."""

from typing import Annotated

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status

from app.models.imports import BankName, UploadCsvResponse
from app.services.imports import store_uploaded_csv

router = APIRouter(prefix="/imports", tags=["imports"])


@router.post(
    "/csv",
    response_model=UploadCsvResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a bank CSV file",
)
async def upload_csv(
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

    return store_uploaded_csv(
        file_bytes=file_bytes,
        original_filename=file.filename,
        bank_name=bank_name,
        account_id=normalized_account_id,
    )
