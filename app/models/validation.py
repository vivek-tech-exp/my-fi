"""Models for import validation reports."""

from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, Field


class ValidationCheckStatus(StrEnum):
    """Status for an individual validation area."""

    PASS = "PASS"
    WARN = "WARN"
    FAIL = "FAIL"
    SKIPPED = "SKIPPED"


class ValidationReportRecord(BaseModel):
    """Validation outcome for a completed import."""

    report_id: UUID
    file_id: UUID
    total_rows: int = Field(ge=0)
    accepted_rows: int = Field(ge=0)
    ignored_rows: int = Field(ge=0)
    suspicious_rows: int = Field(ge=0)
    duplicate_rows: int = Field(ge=0)
    transactions_imported: int = Field(ge=0)
    reconciliation_status: ValidationCheckStatus
    ledger_continuity_status: ValidationCheckStatus
    final_status: str
    messages: list[str] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
