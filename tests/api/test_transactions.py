"""Tests for canonical transaction inspection endpoints."""

from datetime import UTC, date, datetime
from uuid import uuid4

from app.db.canonical_transactions import insert_canonical_transactions
from fastapi.testclient import TestClient
from tests.factories import canonical_transaction


def test_get_transactions_returns_empty_ledger(client: TestClient) -> None:
    response = client.get("/transactions")

    assert response.status_code == 200
    assert response.json() == []


def test_get_transactions_lists_and_filters_canonical_rows(client: TestClient) -> None:
    source_file_id = uuid4()
    transactions = [
        canonical_transaction(
            source_file_id=source_file_id,
            bank_name="hdfc",
            account_id="primary",
            transaction_date=date(2026, 4, 2),
            fingerprint="1" * 64,
            created_at=datetime(2026, 4, 2, tzinfo=UTC),
        ),
        canonical_transaction(
            bank_name="hdfc",
            account_id="secondary",
            transaction_date=date(2026, 4, 3),
            fingerprint="2" * 64,
            created_at=datetime(2026, 4, 3, tzinfo=UTC),
        ),
        canonical_transaction(
            bank_name="federal",
            account_id="primary",
            transaction_date=date(2026, 4, 4),
            fingerprint="3" * 64,
            created_at=datetime(2026, 4, 4, tzinfo=UTC),
        ),
    ]
    insert_canonical_transactions(transactions)

    all_response = client.get("/transactions")
    hdfc_response = client.get("/transactions", params={"bank_name": "hdfc"})
    account_response = client.get("/transactions", params={"account_id": "primary"})
    source_response = client.get("/transactions", params={"source_file_id": str(source_file_id)})
    date_response = client.get(
        "/transactions",
        params={
            "transaction_date_from": "2026-04-03",
            "transaction_date_to": "2026-04-04",
        },
    )
    page_response = client.get("/transactions", params={"limit": 1, "offset": 1})

    assert all_response.status_code == 200
    assert len(all_response.json()) == 3
    assert all_response.json()[0]["transaction_date"] == "2026-04-04"
    assert hdfc_response.status_code == 200
    assert len(hdfc_response.json()) == 2
    assert account_response.status_code == 200
    assert len(account_response.json()) == 2
    assert source_response.status_code == 200
    assert len(source_response.json()) == 1
    assert source_response.json()[0]["source_file_id"] == str(source_file_id)
    assert date_response.status_code == 200
    assert len(date_response.json()) == 2
    assert page_response.status_code == 200
    assert len(page_response.json()) == 1
    assert page_response.json()[0]["transaction_date"] == "2026-04-03"


def test_get_transactions_rejects_invalid_date_range(client: TestClient) -> None:
    response = client.get(
        "/transactions",
        params={
            "transaction_date_from": "2026-04-10",
            "transaction_date_to": "2026-04-01",
        },
    )

    assert response.status_code == 400
    assert response.json() == {
        "detail": "'transaction_date_from' cannot be after 'transaction_date_to'."
    }
