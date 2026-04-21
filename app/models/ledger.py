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
