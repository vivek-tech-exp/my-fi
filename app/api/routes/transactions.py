"""Routes for canonical transaction ledger inspection."""

from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from app.db.canonical_transactions import list_canonical_transactions
from app.models.imports import BankName
from app.models.ledger import CanonicalTransactionRecord

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
        source_file_id=source_file_id,
        transaction_date_from=transaction_date_from,
        transaction_date_to=transaction_date_to,
        limit=limit,
        offset=offset,
    )
