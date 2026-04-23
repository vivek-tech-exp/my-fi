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


class ValidationIssueSeverity(StrEnum):
    """User-facing validation issue severity."""

    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class ValidationIssueRecord(BaseModel):
    """Structured validation issue for UI inspection and filtering."""

    severity: ValidationIssueSeverity
    code: str = Field(min_length=1)
    title: str = Field(min_length=1)
    detail: str = Field(min_length=1)
    suggested_action: str = Field(min_length=1)
    affected_row_count: int = Field(default=0, ge=0)


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
    issues: list[ValidationIssueRecord] = Field(default_factory=list)
    messages: list[str] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    def model_post_init(self, __context: object) -> None:
        """Keep old persisted reports inspectable by deriving generic issues."""

        del __context
        if not self.issues and self.messages:
            self.issues = [_generic_issue_from_message(message) for message in self.messages]
        if not self.messages and self.issues:
            self.messages = [issue.detail for issue in self.issues]


def _generic_issue_from_message(message: str) -> ValidationIssueRecord:
    normalized = message.lower()
    if any(token in normalized for token in ("no ", "could not", "non-positive", "after")):
        severity = ValidationIssueSeverity.ERROR
        title = "Import needs review"
        action = "Review the import report and diagnostics before trusting this file."
    elif any(token in normalized for token in ("warning", "suspicious", "duplicate", "mismatch")):
        severity = ValidationIssueSeverity.WARNING
        title = "Review warning"
        action = "Inspect the affected rows or transactions before relying on this import."
    else:
        severity = ValidationIssueSeverity.INFO
        title = "Import information"
        action = "No action is required."

    return ValidationIssueRecord(
        severity=severity,
        code="legacy_message",
        title=title,
        detail=message,
        suggested_action=action,
    )
