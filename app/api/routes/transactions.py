"""Routes for canonical transaction ledger inspection."""

from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from app.db.canonical_transactions import (
    list_canonical_transactions,
    summarize_canonical_transactions,
)
from app.models.imports import BankName
from app.models.ledger import (
    CanonicalTransactionRecord,
    TransactionDirection,
    TransactionSummaryGroupBy,
    TransactionSummaryRecord,
)

router = APIRouter(prefix="/transactions", tags=["transactions"])


@router.get(
    "",
    response_model=list[CanonicalTransactionRecord],
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
) -> list[CanonicalTransactionRecord]:
    if (
        transaction_date_from is not None
        and transaction_date_to is not None
        and transaction_date_from > transaction_date_to
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="'transaction_date_from' cannot be after 'transaction_date_to'.",
        )

    return list_canonical_transactions(
        bank_name=bank_name.value if bank_name is not None else None,
        account_id=account_id.strip() or None if account_id else None,
        direction=direction,
        source_file_id=source_file_id,
        transaction_date_from=transaction_date_from,
        transaction_date_to=transaction_date_to,
        limit=limit,
        offset=offset,
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
) -> list[TransactionSummaryRecord]:
    if (
        transaction_date_from is not None
        and transaction_date_to is not None
        and transaction_date_from > transaction_date_to
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="'transaction_date_from' cannot be after 'transaction_date_to'.",
        )

    return summarize_canonical_transactions(
        group_by=group_by,
        bank_name=bank_name.value if bank_name is not None else None,
        account_id=account_id.strip() or None if account_id else None,
        direction=direction,
        source_file_id=source_file_id,
        transaction_date_from=transaction_date_from,
        transaction_date_to=transaction_date_to,
        limit=limit,
        offset=offset,
    )
