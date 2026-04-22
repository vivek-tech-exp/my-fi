"""Tests for canonical transaction inspection endpoints."""

from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import uuid4

from app.db.canonical_transactions import insert_canonical_transactions
from app.models.ledger import TransactionDirection
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
            direction=TransactionDirection.CREDIT,
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
    debit_response = client.get("/transactions", params={"direction": "DEBIT"})
    credit_response = client.get("/transactions", params={"direction": "CREDIT"})
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
    assert debit_response.status_code == 200
    assert len(debit_response.json()) == 2
    assert credit_response.status_code == 200
    assert len(credit_response.json()) == 1
    assert credit_response.json()[0]["direction"] == "CREDIT"
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


def test_get_transactions_summary_groups_monthly_totals(client: TestClient) -> None:
    transactions = [
        canonical_transaction(
            bank_name="hdfc",
            account_id="primary",
            transaction_date=date(2026, 4, 2),
            amount=Decimal("120.00"),
            direction=TransactionDirection.DEBIT,
            fingerprint="4" * 64,
            created_at=datetime(2026, 4, 2, tzinfo=UTC),
        ),
        canonical_transaction(
            bank_name="hdfc",
            account_id="primary",
            transaction_date=date(2026, 4, 15),
            amount=Decimal("50.00"),
            direction=TransactionDirection.CREDIT,
            fingerprint="5" * 64,
            created_at=datetime(2026, 4, 15, tzinfo=UTC),
        ),
        canonical_transaction(
            bank_name="hdfc",
            account_id="primary",
            transaction_date=date(2026, 5, 1),
            amount=Decimal("20.00"),
            direction=TransactionDirection.DEBIT,
            fingerprint="6" * 64,
            created_at=datetime(2026, 5, 1, tzinfo=UTC),
        ),
    ]
    insert_canonical_transactions(transactions)

    response = client.get(
        "/transactions/summary",
        params={
            "group_by": "month",
            "bank_name": "hdfc",
            "direction": "DEBIT",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 2
    assert payload[0]["period_start"] == "2026-05-01"
    assert payload[0]["group_by"] == "month"
    assert payload[0]["transaction_count"] == 1
    assert payload[0]["debit_total"] == "20.00"
    assert payload[0]["credit_total"] == "0.00"
    assert payload[0]["net_amount"] == "-20.00"
    assert payload[1]["period_start"] == "2026-04-01"
    assert payload[1]["transaction_count"] == 1
    assert payload[1]["debit_total"] == "120.00"
    assert payload[1]["net_amount"] == "-120.00"


def test_get_transactions_summary_rejects_invalid_date_range(client: TestClient) -> None:
    response = client.get(
        "/transactions/summary",
        params={
            "transaction_date_from": "2026-04-10",
            "transaction_date_to": "2026-04-01",
        },
    )

    assert response.status_code == 400
    assert response.json() == {
        "detail": "'transaction_date_from' cannot be after 'transaction_date_to'."
    }
