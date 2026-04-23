"""Models for parser inspection, raw-row audit trails, and parser outputs."""

from datetime import date
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.ledger import CanonicalTransactionRecord


class RawRowType(StrEnum):
    """Classification for a raw statement row after parser inspection."""

    ACCEPTED = "accepted"
    IGNORED = "ignored"
    SUSPICIOUS = "suspicious"


class RawRowRepairStatus(StrEnum):
    """User-facing repair outcome for a raw row."""

    NOT_REQUIRED = "not_required"
    REPAIRED = "repaired"
    NOT_REPAIRABLE = "not_repairable"
    NOT_ATTEMPTED = "not_attempted"


class RawRowRecord(BaseModel):
    """Persisted audit record for a single inspected row."""

    raw_row_id: UUID
    file_id: UUID
    row_number: int = Field(ge=1)
    parser_name: str = Field(min_length=1)
    parser_version: str = Field(min_length=1)
    row_type: RawRowType
    raw_text: str
    normalized_text: str | None = None
    raw_payload: list[str] | None = None
    rejection_reason: str | None = None
    header_row: bool = False
    repaired_row: bool = False
    repair_status: RawRowRepairStatus = RawRowRepairStatus.NOT_REQUIRED

    def model_post_init(self, __context: object) -> None:
        """Derive the user-facing repair outcome after validation."""

        del __context
        self.repair_status = self._derive_repair_status()

    def _derive_repair_status(self) -> RawRowRepairStatus:
        if self.repaired_row:
            return RawRowRepairStatus.REPAIRED

        if self.row_type != RawRowType.SUSPICIOUS:
            return RawRowRepairStatus.NOT_REQUIRED

        if self.rejection_reason in {"column_count_mismatch", "invalid_amount_shape"}:
            return RawRowRepairStatus.NOT_REPAIRABLE

        return RawRowRepairStatus.NOT_ATTEMPTED


class RawRowAuditSummary(BaseModel):
    """Aggregate counters for raw-row inspection."""

    header_detected: bool = False
    raw_rows_recorded: int = Field(default=0, ge=0)
    accepted_rows_recorded: int = Field(default=0, ge=0)
    ignored_rows_recorded: int = Field(default=0, ge=0)
    suspicious_rows_recorded: int = Field(default=0, ge=0)


class ParserInspectionResult(RawRowAuditSummary):
    """Full parser result including raw-row inspection and canonical mappings."""

    parser_name: str = Field(min_length=1)
    parser_version: str = Field(min_length=1)
    header_row_number: int | None = Field(default=None, ge=1)
    detected_account_id: str | None = None
    statement_start_date: date | None = None
    statement_end_date: date | None = None
    duplicate_transactions_detected: int = Field(default=0, ge=0)
    exact_duplicate_transactions: int = Field(default=0, ge=0)
    probable_duplicate_transactions: int = Field(default=0, ge=0)
    ambiguous_transactions_detected: int = Field(default=0, ge=0)
    raw_rows: list[RawRowRecord] = Field(default_factory=list)
    canonical_transactions: list[CanonicalTransactionRecord] = Field(default_factory=list)

    def add_row(self, row: RawRowRecord) -> None:
        """Track a single raw-row audit record and update summary counters."""

        self.raw_rows.append(row)
        self.raw_rows_recorded += 1

        if row.header_row and self.header_row_number is None:
            self.header_detected = True
            self.header_row_number = row.row_number

        if row.row_type == RawRowType.ACCEPTED:
            self.accepted_rows_recorded += 1
        elif row.row_type == RawRowType.IGNORED:
            self.ignored_rows_recorded += 1
        else:
            self.suspicious_rows_recorded += 1

    @property
    def transactions_imported(self) -> int:
        """Return the number of canonical transactions produced by the parser."""

        return len(self.canonical_transactions)
