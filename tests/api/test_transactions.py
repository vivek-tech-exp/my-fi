"""Tests for canonical transaction inspection endpoints."""

from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import uuid4

from app.db import source_files as source_files_repo
from app.db.canonical_transactions import insert_canonical_transactions
from app.models.imports import BankName, ImportStatus
from app.models.ledger import DuplicateConfidence, TransactionDirection
from fastapi.testclient import TestClient
from tests.factories import canonical_transaction, source_file_record


def test_get_transactions_returns_empty_ledger(client: TestClient) -> None:
    response = client.get("/transactions")

    assert response.status_code == 200
    assert response.json() == {
        "items": [],
        "total": 0,
        "limit": 100,
        "offset": 0,
        "has_next": False,
        "has_previous": False,
    }


def test_get_transactions_lists_and_filters_canonical_rows(client: TestClient) -> None:
    source_file_id = uuid4()
    source_files_repo.insert_source_file(
        source_file_record(
            file_id=source_file_id,
            bank_name=BankName.HDFC,
            file_hash="4" * 64,
            import_status=ImportStatus.PASS,
        )
    )
    transactions = [
        canonical_transaction(
            source_file_id=source_file_id,
            bank_name="hdfc",
            account_id="primary",
            transaction_date=date(2026, 4, 2),
            description_raw="UPI/CAFE BREWSOME",
            fingerprint="1" * 64,
            created_at=datetime(2026, 4, 2, tzinfo=UTC),
        ),
        canonical_transaction(
            bank_name="hdfc",
            account_id="secondary",
            transaction_date=date(2026, 4, 3),
            direction=TransactionDirection.CREDIT,
            amount=Decimal("200.00"),
            balance=None,
            description_raw="Salary April",
            fingerprint="2" * 64,
            duplicate_confidence=DuplicateConfidence.AMBIGUOUS,
            created_at=datetime(2026, 4, 3, tzinfo=UTC),
        ),
        canonical_transaction(
            bank_name="federal",
            account_id="primary",
            transaction_date=date(2026, 4, 4),
            amount=Decimal("300.00"),
            description_raw="Rent payment",
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
    search_response = client.get("/transactions", params={"description_contains": "salary"})
    amount_response = client.get(
        "/transactions",
        params={"amount_min": "150.00", "amount_max": "250.00"},
    )
    duplicate_response = client.get(
        "/transactions",
        params={"duplicate_confidence": "AMBIGUOUS"},
    )
    has_balance_response = client.get("/transactions", params={"has_balance": "true"})
    missing_balance_response = client.get("/transactions", params={"has_balance": "false"})
    date_response = client.get(
        "/transactions",
        params={
            "transaction_date_from": "2026-04-03",
            "transaction_date_to": "2026-04-04",
        },
    )
    page_response = client.get("/transactions", params={"limit": 1, "offset": 1})

    assert all_response.status_code == 200
    all_payload = all_response.json()
    assert all_payload["total"] == 3
    assert all_payload["limit"] == 100
    assert all_payload["offset"] == 0
    assert all_payload["has_next"] is False
    assert len(all_payload["items"]) == 3
    assert all_payload["items"][0]["transaction_date"] == "2026-04-04"
    assert hdfc_response.status_code == 200
    assert hdfc_response.json()["total"] == 2
    assert account_response.status_code == 200
    assert account_response.json()["total"] == 2
    assert source_response.status_code == 200
    assert source_response.json()["total"] == 1
    assert source_response.json()["items"][0]["source_file_id"] == str(source_file_id)
    assert source_response.json()["items"][0]["source_filename"] == "statement.csv"
    assert source_response.json()["items"][0]["source_import_status"] == "PASS"
    assert debit_response.status_code == 200
    assert debit_response.json()["total"] == 2
    assert credit_response.status_code == 200
    assert credit_response.json()["total"] == 1
    assert credit_response.json()["items"][0]["direction"] == "CREDIT"
    assert search_response.status_code == 200
    assert search_response.json()["total"] == 1
    assert search_response.json()["items"][0]["description_raw"] == "Salary April"
    assert amount_response.status_code == 200
    assert amount_response.json()["total"] == 1
    assert amount_response.json()["items"][0]["amount"] == "200.00"
    assert duplicate_response.status_code == 200
    assert duplicate_response.json()["total"] == 1
    assert duplicate_response.json()["items"][0]["duplicate_confidence"] == "AMBIGUOUS"
    assert has_balance_response.status_code == 200
    assert has_balance_response.json()["total"] == 2
    assert missing_balance_response.status_code == 200
    assert missing_balance_response.json()["total"] == 1
    assert date_response.status_code == 200
    assert date_response.json()["total"] == 2
    assert page_response.status_code == 200
    assert page_response.json()["total"] == 3
    assert len(page_response.json()["items"]) == 1
    assert page_response.json()["has_next"] is True
    assert page_response.json()["has_previous"] is True
    assert page_response.json()["items"][0]["transaction_date"] == "2026-04-03"


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


def test_get_transactions_rejects_invalid_amount_range(client: TestClient) -> None:
    response = client.get(
        "/transactions",
        params={
            "amount_min": "10.00",
            "amount_max": "1.00",
        },
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "'amount_min' cannot be greater than 'amount_max'."}


def test_get_transactions_summary_groups_monthly_totals(client: TestClient) -> None:
    transactions = [
        canonical_transaction(
            bank_name="hdfc",
            account_id="primary",
            transaction_date=date(2026, 4, 2),
            amount=Decimal("120.00"),
            direction=TransactionDirection.DEBIT,
            balance=Decimal("880.00"),
            fingerprint="4" * 64,
            created_at=datetime(2026, 4, 2, tzinfo=UTC),
        ),
        canonical_transaction(
            bank_name="hdfc",
            account_id="primary",
            transaction_date=date(2026, 4, 15),
            amount=Decimal("50.00"),
            direction=TransactionDirection.CREDIT,
            balance=Decimal("930.00"),
            fingerprint="5" * 64,
            created_at=datetime(2026, 4, 15, tzinfo=UTC),
        ),
        canonical_transaction(
            bank_name="hdfc",
            account_id="primary",
            transaction_date=date(2026, 5, 1),
            amount=Decimal("20.00"),
            direction=TransactionDirection.DEBIT,
            balance=Decimal("910.00"),
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
    assert payload[0]["debit_count"] == 1
    assert payload[0]["credit_count"] == 0
    assert payload[0]["debit_total"] == "20.00"
    assert payload[0]["credit_total"] == "0.00"
    assert payload[0]["net_amount"] == "-20.00"
    assert payload[0]["opening_balance"] == "910.00"
    assert payload[0]["closing_balance"] == "910.00"
    assert payload[1]["period_start"] == "2026-04-01"
    assert payload[1]["transaction_count"] == 1
    assert payload[1]["debit_count"] == 1
    assert payload[1]["debit_total"] == "120.00"
    assert payload[1]["net_amount"] == "-120.00"
    assert payload[1]["opening_balance"] == "880.00"
    assert payload[1]["closing_balance"] == "880.00"


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
