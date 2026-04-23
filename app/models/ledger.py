"""Models for canonical transaction storage."""

from datetime import UTC, date, datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, Field


class TransactionDirection(StrEnum):
    """Canonical direction for a normalized transaction."""

    DEBIT = "DEBIT"
    CREDIT = "CREDIT"


class DuplicateConfidence(StrEnum):
    """Duplicate-confidence placeholder until ledger dedupe is implemented."""

    UNIQUE = "UNIQUE"
    EXACT_DUPLICATE = "EXACT_DUPLICATE"
    PROBABLE_DUPLICATE = "PROBABLE_DUPLICATE"
    AMBIGUOUS = "AMBIGUOUS"


class TransactionSummaryGroupBy(StrEnum):
    """Supported aggregation dimensions for transaction summaries."""

    MONTH = "month"


class CanonicalTransactionRecord(BaseModel):
    """Trusted canonical transaction derived from an accepted raw row."""

    transaction_id: UUID
    source_file_id: UUID
    raw_row_id: UUID
    bank_name: str = Field(min_length=1)
    account_id: str | None = None
    transaction_date: date
    value_date: date | None = None
    description_raw: str = Field(min_length=1)
    amount: Decimal
    direction: TransactionDirection
    balance: Decimal | None = None
    currency: str = Field(default="INR", min_length=3, max_length=3)
    source_row_number: int = Field(ge=1)
    reference_number: str | None = None
    transaction_fingerprint: str = Field(min_length=64, max_length=64)
    duplicate_confidence: DuplicateConfidence = DuplicateConfidence.UNIQUE
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class CanonicalTransactionViewRecord(CanonicalTransactionRecord):
    """Canonical transaction enriched with source import context for UI inspection."""

    source_filename: str | None = None
    source_import_status: str | None = None
    source_statement_start_date: date | None = None
    source_statement_end_date: date | None = None


class TransactionListResponse(BaseModel):
    """Paginated transaction list response."""

    items: list[CanonicalTransactionViewRecord] = Field(default_factory=list)
    total: int = Field(ge=0)
    limit: int = Field(ge=1)
    offset: int = Field(ge=0)
    has_next: bool
    has_previous: bool


class TransactionSummaryRecord(BaseModel):
    """Aggregated transaction metrics for a grouped ledger period."""

    period_start: date
    group_by: TransactionSummaryGroupBy
    transaction_count: int = Field(ge=0)
    debit_count: int = Field(ge=0)
    credit_count: int = Field(ge=0)
    debit_total: Decimal
    credit_total: Decimal
    net_amount: Decimal
    opening_balance: Decimal | None = None
    closing_balance: Decimal | None = None
