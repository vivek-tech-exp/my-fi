"""Routes for canonical transaction ledger inspection."""

from datetime import date
from decimal import Decimal
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from app.db.canonical_transactions import (
    count_canonical_transactions,
    list_canonical_transactions,
    summarize_canonical_transactions,
)
from app.models.imports import BankName
from app.models.ledger import (
    DuplicateConfidence,
    TransactionDirection,
    TransactionListResponse,
    TransactionSummaryGroupBy,
    TransactionSummaryRecord,
)

router = APIRouter(prefix="/transactions", tags=["transactions"])


@router.get(
    "",
    response_model=TransactionListResponse,
    summary="List canonical ledger transactions",
)
def get_transactions(
    bank_name: Annotated[
        BankName | None,
        Query(description="Optional bank filter"),
    ] = None,
    account_id: Annotated[
        str | None,
        Query(description="Optional account identifier filter"),
    ] = None,
    direction: Annotated[
        TransactionDirection | None,
        Query(description="Optional direction filter"),
    ] = None,
    description_contains: Annotated[
        str | None,
        Query(description="Search narration or reference text"),
    ] = None,
    amount_min: Annotated[
        Decimal | None,
        Query(description="Optional inclusive lower amount bound"),
    ] = None,
    amount_max: Annotated[
        Decimal | None,
        Query(description="Optional inclusive upper amount bound"),
    ] = None,
    duplicate_confidence: Annotated[
        DuplicateConfidence | None,
        Query(description="Optional duplicate-confidence filter"),
    ] = None,
    has_balance: Annotated[
        bool | None,
        Query(description="Filter transactions with or without balance values"),
    ] = None,
    source_file_id: Annotated[
        UUID | None,
        Query(description="Optional source file filter"),
    ] = None,
    transaction_date_from: Annotated[
        date | None,
        Query(description="Optional inclusive lower bound for transaction date"),
    ] = None,
    transaction_date_to: Annotated[
        date | None,
        Query(description="Optional inclusive upper bound for transaction date"),
    ] = None,
    limit: Annotated[int, Query(ge=1, le=1000)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> TransactionListResponse:
    _validate_transaction_filters(
        transaction_date_from=transaction_date_from,
        transaction_date_to=transaction_date_to,
        amount_min=amount_min,
        amount_max=amount_max,
    )

    normalized_bank_name = bank_name.value if bank_name is not None else None
    normalized_account_id = account_id.strip() or None if account_id else None
    normalized_description = description_contains.strip() or None if description_contains else None
    total = count_canonical_transactions(
        bank_name=normalized_bank_name,
        account_id=normalized_account_id,
        direction=direction,
        description_contains=normalized_description,
        amount_min=amount_min,
        amount_max=amount_max,
        duplicate_confidence=duplicate_confidence,
        has_balance=has_balance,
        source_file_id=source_file_id,
        transaction_date_from=transaction_date_from,
        transaction_date_to=transaction_date_to,
    )
    items = list_canonical_transactions(
        bank_name=normalized_bank_name,
        account_id=normalized_account_id,
        direction=direction,
        description_contains=normalized_description,
        amount_min=amount_min,
        amount_max=amount_max,
        duplicate_confidence=duplicate_confidence,
        has_balance=has_balance,
        source_file_id=source_file_id,
        transaction_date_from=transaction_date_from,
        transaction_date_to=transaction_date_to,
        limit=limit,
        offset=offset,
    )

    return TransactionListResponse(
        items=items,
        total=total,
        limit=limit,
        offset=offset,
        has_next=offset + len(items) < total,
        has_previous=offset > 0,
    )


@router.get(
    "/summary",
    response_model=list[TransactionSummaryRecord],
    summary="Summarize canonical ledger transactions",
)
def get_transactions_summary(
    group_by: Annotated[
        TransactionSummaryGroupBy,
        Query(description="Aggregation dimension"),
    ] = TransactionSummaryGroupBy.MONTH,
    bank_name: Annotated[
        BankName | None,
        Query(description="Optional bank filter"),
    ] = None,
    account_id: Annotated[
        str | None,
        Query(description="Optional account identifier filter"),
    ] = None,
    direction: Annotated[
        TransactionDirection | None,
        Query(description="Optional direction filter"),
    ] = None,
    description_contains: Annotated[
        str | None,
        Query(description="Search narration or reference text"),
    ] = None,
    amount_min: Annotated[
        Decimal | None,
        Query(description="Optional inclusive lower amount bound"),
    ] = None,
    amount_max: Annotated[
        Decimal | None,
        Query(description="Optional inclusive upper amount bound"),
    ] = None,
    duplicate_confidence: Annotated[
        DuplicateConfidence | None,
        Query(description="Optional duplicate-confidence filter"),
    ] = None,
    has_balance: Annotated[
        bool | None,
        Query(description="Filter transactions with or without balance values"),
    ] = None,
    source_file_id: Annotated[
        UUID | None,
        Query(description="Optional source file filter"),
    ] = None,
    transaction_date_from: Annotated[
        date | None,
        Query(description="Optional inclusive lower bound for transaction date"),
    ] = None,
    transaction_date_to: Annotated[
        date | None,
        Query(description="Optional inclusive upper bound for transaction date"),
    ] = None,
    limit: Annotated[int, Query(ge=1, le=1000)] = 1000,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[TransactionSummaryRecord]:
    _validate_transaction_filters(
        transaction_date_from=transaction_date_from,
        transaction_date_to=transaction_date_to,
        amount_min=amount_min,
        amount_max=amount_max,
    )

    return summarize_canonical_transactions(
        group_by=group_by,
        bank_name=bank_name.value if bank_name is not None else None,
        account_id=account_id.strip() or None if account_id else None,
        direction=direction,
        description_contains=description_contains.strip() or None if description_contains else None,
        amount_min=amount_min,
        amount_max=amount_max,
        duplicate_confidence=duplicate_confidence,
        has_balance=has_balance,
        source_file_id=source_file_id,
        transaction_date_from=transaction_date_from,
        transaction_date_to=transaction_date_to,
        limit=limit,
        offset=offset,
    )


def _validate_transaction_filters(
    *,
    transaction_date_from: date | None,
    transaction_date_to: date | None,
    amount_min: Decimal | None,
    amount_max: Decimal | None,
) -> None:
    if (
        transaction_date_from is not None
        and transaction_date_to is not None
        and transaction_date_from > transaction_date_to
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="'transaction_date_from' cannot be after 'transaction_date_to'.",
        )

    if amount_min is not None and amount_max is not None and amount_min > amount_max:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="'amount_min' cannot be greater than 'amount_max'.",
        )
