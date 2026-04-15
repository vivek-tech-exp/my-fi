"""Models for import upload flows."""

from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, Field


class BankName(StrEnum):
    """Supported banks for V1 ingestion."""

    HDFC = "hdfc"
    KOTAK = "kotak"
    FEDERAL = "federal"


class ImportStatus(StrEnum):
    """Upload and processing lifecycle states."""

    RECEIVED = "RECEIVED"


class UploadCsvResponse(BaseModel):
    """Structured response for a stored CSV upload."""

    file_id: UUID
    file_hash: str = Field(min_length=64, max_length=64)
    bank_name: BankName
    account_id: str | None = None
    original_filename: str
    stored_path: str
    file_size_bytes: int = Field(ge=1)
    status: ImportStatus
    uploaded_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    message: str
