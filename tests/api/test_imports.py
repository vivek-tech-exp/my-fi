"""Tests for the CSV upload endpoint."""

import json
from datetime import date
from decimal import Decimal
from hashlib import sha256
from pathlib import Path

import duckdb
from app.core.config import Settings
from fastapi.testclient import TestClient


def test_upload_csv_persists_file_and_returns_metadata(
    client: TestClient,
    settings: Settings,
) -> None:
    file_bytes = b"Date,Narration,Debit,Credit,Balance\n2026-04-01,Salary,,1000.00,1000.00\n"

    response = client.post(
        "/imports/csv",
        data={"bank_name": "hdfc", "account_id": "primary-checking"},
        files={"file": ("salary_statement.csv", file_bytes, "text/csv")},
    )

    assert response.status_code == 201
    payload = response.json()
    stored_path = Path(payload["stored_path"])

    assert payload["bank_name"] == "hdfc"
    assert payload["account_id"] == "primary-checking"
    assert payload["original_filename"] == "salary_statement.csv"
    assert payload["file_hash"] == sha256(file_bytes).hexdigest()
    assert payload["duplicate_file"] is False
    assert payload["file_size_bytes"] == len(file_bytes)
    assert payload["parser_version"] == settings.default_parser_version
    assert payload["parser_name"] == "hdfc_csv_parser"
    assert payload["status"] == "RECEIVED"
    assert payload["statement_start_date"] is None
    assert payload["statement_end_date"] is None
    assert payload["encoding_detected"] == "utf-8"
    assert payload["delimiter_detected"] == ","
    assert payload["header_detected"] is True
    assert payload["raw_rows_recorded"] == 2
    assert payload["suspicious_rows_recorded"] == 0
    assert payload["transactions_imported"] == 0
    assert payload["duplicate_transactions_detected"] == 0
    assert payload["exact_duplicate_transactions"] == 0
    assert payload["probable_duplicate_transactions"] == 0
    assert payload["ambiguous_transactions_detected"] == 0
    assert payload["message"].startswith("File stored locally, raw rows were audited")
    assert stored_path.exists()
    assert stored_path.read_bytes() == file_bytes
    assert "hdfc" in stored_path.parts
    assert stored_path.name.startswith(payload["file_hash"])

    with duckdb.connect(str(settings.database_path), read_only=True) as connection:
        row = connection.execute(
            """
            SELECT
                bank_name,
                account_id,
                original_filename,
                stored_path,
                file_hash,
                file_size_bytes,
                parser_version,
                import_status,
                statement_start_date,
                statement_end_date,
                encoding_detected,
                delimiter_detected
            FROM source_files
            WHERE file_id = ?
            """,
            [payload["file_id"]],
        ).fetchone()

    assert row is not None
    assert row[0] == "hdfc"
    assert row[1] == "primary-checking"
    assert row[2] == "salary_statement.csv"
    assert row[3] == payload["stored_path"]
    assert row[4] == payload["file_hash"]
    assert row[5] == len(file_bytes)
    assert row[6] == settings.default_parser_version
    assert row[7] == "RECEIVED"
    assert row[8] is None
    assert row[9] is None
    assert row[10] == "utf-8"
    assert row[11] == ","

    with duckdb.connect(str(settings.database_path), read_only=True) as connection:
        raw_rows = connection.execute(
            """
            SELECT
                row_number,
                parser_name,
                parser_version,
                row_type,
                raw_text,
                raw_payload,
                rejection_reason,
                header_row,
                repaired_row
            FROM raw_rows
            WHERE file_id = ?
            ORDER BY row_number
            """,
            [payload["file_id"]],
        ).fetchall()

    assert len(raw_rows) == 2
    assert raw_rows[0][0] == 1
    assert raw_rows[0][1] == "hdfc_csv_parser"
    assert raw_rows[0][2] == settings.default_parser_version
    assert raw_rows[0][3] == "ignored"
    assert raw_rows[0][4] == "Date,Narration,Debit,Credit,Balance"
    assert json.loads(raw_rows[0][5]) == ["Date", "Narration", "Debit", "Credit", "Balance"]
    assert raw_rows[0][6] == "header_row"
    assert raw_rows[0][7] is True
    assert raw_rows[0][8] is False

    assert raw_rows[1][0] == 2
    assert raw_rows[1][1] == "hdfc_csv_parser"
    assert raw_rows[1][3] == "accepted"
    assert raw_rows[1][4] == "2026-04-01,Salary,,1000.00,1000.00"
    assert json.loads(raw_rows[1][5]) == ["2026-04-01", "Salary", "", "1000.00", "1000.00"]
    assert raw_rows[1][6] is None
    assert raw_rows[1][7] is False
    assert raw_rows[1][8] is False


def test_upload_csv_rejects_empty_files(client: TestClient) -> None:
    response = client.post(
        "/imports/csv",
        data={"bank_name": "kotak"},
        files={"file": ("empty.csv", b"", "text/csv")},
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "Uploaded file is empty."}


def test_upload_csv_rejects_unknown_bank_name(client: TestClient) -> None:
    response = client.post(
        "/imports/csv",
        data={"bank_name": "unknown-bank"},
        files={"file": ("statement.csv", b"header\nrow\n", "text/csv")},
    )

    assert response.status_code == 422


def test_upload_csv_creates_database_file(client: TestClient, settings: Settings) -> None:
    response = client.post(
        "/imports/csv",
        data={"bank_name": "federal"},
        files={"file": ("statement.csv", b"header\nrow\n", "text/csv")},
    )

    assert response.status_code == 201
    assert settings.database_path.exists()


def test_upload_csv_returns_existing_record_for_duplicate_file(
    client: TestClient,
    settings: Settings,
) -> None:
    file_bytes = b"Date,Narration,Debit,Credit,Balance\n2026-04-01,Salary,,1000.00,1000.00\n"

    first_response = client.post(
        "/imports/csv",
        data={"bank_name": "hdfc", "account_id": "primary-checking"},
        files={"file": ("salary_statement.csv", file_bytes, "text/csv")},
    )
    second_response = client.post(
        "/imports/csv",
        data={"bank_name": "hdfc", "account_id": "secondary-account"},
        files={"file": ("renamed_statement.csv", file_bytes, "text/csv")},
    )

    assert first_response.status_code == 201
    assert second_response.status_code == 200

    first_payload = first_response.json()
    second_payload = second_response.json()

    assert second_payload["duplicate_file"] is True
    assert second_payload["file_id"] == first_payload["file_id"]
    assert second_payload["file_hash"] == first_payload["file_hash"]
    assert second_payload["stored_path"] == first_payload["stored_path"]
    assert second_payload["account_id"] == "primary-checking"
    assert second_payload["parser_name"] == "hdfc_csv_parser"
    assert second_payload["encoding_detected"] == "utf-8"
    assert second_payload["delimiter_detected"] == ","
    assert second_payload["header_detected"] is True
    assert second_payload["raw_rows_recorded"] == 2
    assert second_payload["suspicious_rows_recorded"] == 0
    assert second_payload["transactions_imported"] == 0
    assert second_payload["duplicate_transactions_detected"] == 0
    assert second_payload["message"].startswith("Matching file already registered.")

    with duckdb.connect(str(settings.database_path), read_only=True) as connection:
        row_count = connection.execute("SELECT COUNT(*) FROM source_files").fetchone()
        raw_row_count = connection.execute("SELECT COUNT(*) FROM raw_rows").fetchone()

    assert row_count is not None
    assert row_count[0] == 1
    assert raw_row_count is not None
    assert raw_row_count[0] == 2


def test_upload_csv_quarantines_unreadable_files(client: TestClient) -> None:
    unreadable_bytes = b"\x81\x8d\x8f\x90"

    response = client.post(
        "/imports/csv",
        data={"bank_name": "kotak"},
        files={"file": ("broken_statement.csv", unreadable_bytes, "text/csv")},
    )

    assert response.status_code == 201
    payload = response.json()
    stored_path = Path(payload["stored_path"])

    assert payload["parser_name"] == "kotak_csv_parser"
    assert payload["status"] == "FAIL_NEEDS_REVIEW"
    assert payload["encoding_detected"] is None
    assert payload["delimiter_detected"] is None
    assert payload["header_detected"] is False
    assert payload["raw_rows_recorded"] == 0
    assert payload["suspicious_rows_recorded"] == 0
    assert payload["transactions_imported"] == 0
    assert payload["duplicate_transactions_detected"] == 0
    assert payload["duplicate_file"] is False
    assert payload["message"].startswith("File was quarantined")
    assert "quarantine" in stored_path.parts
    assert stored_path.exists()
    assert stored_path.read_bytes() == unreadable_bytes


def test_upload_csv_imports_kotak_transactions_into_canonical_ledger(
    client: TestClient,
    settings: Settings,
) -> None:
    file_bytes = (
        b'"",,Account Statement\n'
        b'"Jharkhand ",,,,Period,From 01/01/2026 To 15/04/2026\n'
        b"Sl. No.,Transaction Date,Value Date,Description,"
        b"Chq / Ref No.,Debit,Credit,Balance,Dr / Cr\n"
        b"1,03-04-2026 19:40:46,03-04-2026,"
        b"UPI/CAFE BREWSOME P/627219443204/resolve interna,"
        b'UPI-609393884269,310.78,,"39,591.75",CR\n'
        b"2,02-04-2026 19:56:53,02-04-2026,"
        b"UPI/MANKONDA VIVEK/120977030678/UPI,"
        b'UPI-609218418071,,"50,000.00","53,053.91",CR\n'
        b'Closing balance,"as on 15/04/2026   INR 53,053.91"\n'
        b"You may call our 24-hour Customer Contact Centre at our number 1860 266 2666\n"
    )

    response = client.post(
        "/imports/csv",
        data={"bank_name": "kotak", "account_id": "travel-fund"},
        files={"file": ("kotak_statement.csv", file_bytes, "text/csv")},
    )

    assert response.status_code == 201
    payload = response.json()

    assert payload["parser_name"] == "kotak_csv_parser"
    assert payload["status"] == "PASS"
    assert payload["header_detected"] is True
    assert payload["raw_rows_recorded"] == 7
    assert payload["suspicious_rows_recorded"] == 0
    assert payload["transactions_imported"] == 2
    assert payload["duplicate_transactions_detected"] == 0
    assert payload["exact_duplicate_transactions"] == 0
    assert payload["probable_duplicate_transactions"] == 0
    assert payload["ambiguous_transactions_detected"] == 0
    assert payload["statement_start_date"] == "2026-01-01"
    assert payload["statement_end_date"] == "2026-04-15"
    assert (
        payload["message"]
        == "File parsed and 2 transactions were imported into the canonical ledger."
    )

    with duckdb.connect(str(settings.database_path), read_only=True) as connection:
        raw_rows = connection.execute(
            """
            SELECT row_number, row_type, rejection_reason, header_row
            FROM raw_rows
            WHERE file_id = ?
            ORDER BY row_number
            """,
            [payload["file_id"]],
        ).fetchall()
        source_file = connection.execute(
            """
            SELECT import_status, statement_start_date, statement_end_date
            FROM source_files
            WHERE file_id = ?
            """,
            [payload["file_id"]],
        ).fetchone()
        canonical_rows = connection.execute(
            """
            SELECT
                bank_name,
                account_id,
                transaction_date,
                value_date,
                description_raw,
                amount,
                direction,
                balance,
                currency,
                source_row_number,
                reference_number,
                duplicate_confidence
            FROM canonical_transactions
            WHERE source_file_id = ?
            ORDER BY source_row_number
            """,
            [payload["file_id"]],
        ).fetchall()

    assert raw_rows == [
        (1, "ignored", "account_metadata", False),
        (2, "ignored", "statement_metadata", False),
        (3, "ignored", "header_row", True),
        (4, "accepted", None, False),
        (5, "accepted", None, False),
        (6, "ignored", "statement_footer", False),
        (7, "ignored", "statement_footer", False),
    ]
    assert source_file == ("PASS", date(2026, 1, 1), date(2026, 4, 15))
    assert canonical_rows == [
        (
            "kotak",
            "travel-fund",
            date(2026, 4, 3),
            date(2026, 4, 3),
            "UPI/CAFE BREWSOME P/627219443204/resolve interna",
            Decimal("310.78"),
            "DEBIT",
            Decimal("39591.75"),
            "INR",
            4,
            "UPI-609393884269",
            "UNIQUE",
        ),
        (
            "kotak",
            "travel-fund",
            date(2026, 4, 2),
            date(2026, 4, 2),
            "UPI/MANKONDA VIVEK/120977030678/UPI",
            Decimal("50000.00"),
            "CREDIT",
            Decimal("53053.91"),
            "INR",
            5,
            "UPI-609218418071",
            "UNIQUE",
        ),
    ]


def test_import_inspection_endpoints_return_reports_and_rows(
    client: TestClient,
) -> None:
    file_bytes = (
        b'"",,Account Statement\n'
        b'"Jharkhand ",,,,Period,From 01/01/2026 To 15/04/2026\n'
        b"Sl. No.,Transaction Date,Value Date,Description,"
        b"Chq / Ref No.,Debit,Credit,Balance,Dr / Cr\n"
        b"1,03-04-2026 19:40:46,03-04-2026,"
        b"UPI/CAFE BREWSOME P/627219443204/resolve interna,"
        b'UPI-609393884269,310.78,,"39,591.75",CR\n'
        b"2,02-04-2026 19:56:53,02-04-2026,"
        b"UPI/MANKONDA VIVEK/120977030678/UPI,"
        b'UPI-609218418071,,"50,000.00","53,053.91",CR\n'
        b'Closing balance,"as on 15/04/2026   INR 53,053.91"\n'
    )

    upload_response = client.post(
        "/imports/csv",
        data={"bank_name": "kotak", "account_id": "travel-fund"},
        files={"file": ("kotak_statement.csv", file_bytes, "text/csv")},
    )

    assert upload_response.status_code == 201
    file_id = upload_response.json()["file_id"]

    list_response = client.get("/imports")
    detail_response = client.get(f"/imports/{file_id}")
    report_response = client.get(f"/imports/{file_id}/report")
    rows_response = client.get(f"/imports/{file_id}/rows")

    assert list_response.status_code == 200
    assert list_response.json()[0]["file_id"] == file_id

    assert detail_response.status_code == 200
    detail_payload = detail_response.json()
    assert detail_payload["file_id"] == file_id
    assert detail_payload["status"] == "PASS"
    assert detail_payload["report"]["transactions_imported"] == 2

    assert report_response.status_code == 200
    report_payload = report_response.json()
    assert report_payload["file_id"] == file_id
    assert report_payload["total_rows"] == 6
    assert report_payload["accepted_rows"] == 2
    assert report_payload["ignored_rows"] == 4
    assert report_payload["suspicious_rows"] == 0
    assert report_payload["transactions_imported"] == 2
    assert report_payload["final_status"] == "PASS"

    assert rows_response.status_code == 200
    rows_payload = rows_response.json()
    assert len(rows_payload) == 6
    assert rows_payload[2]["header_row"] is True
    assert rows_payload[3]["row_type"] == "accepted"


def test_upload_csv_skips_exact_duplicate_transactions_from_overlapping_kotak_file(
    client: TestClient,
    settings: Settings,
) -> None:
    first_file_bytes = (
        b'"",,Account Statement\n'
        b'"Jharkhand ",,,,Period,From 01/01/2026 To 15/04/2026\n'
        b"Sl. No.,Transaction Date,Value Date,Description,"
        b"Chq / Ref No.,Debit,Credit,Balance,Dr / Cr\n"
        b"1,03-04-2026 19:40:46,03-04-2026,"
        b"UPI/CAFE BREWSOME P/627219443204/resolve interna,"
        b'UPI-609393884269,310.78,,"39,591.75",CR\n'
        b"2,02-04-2026 19:56:53,02-04-2026,"
        b"UPI/MANKONDA VIVEK/120977030678/UPI,"
        b'UPI-609218418071,,"50,000.00","53,053.91",CR\n'
        b'Closing balance,"as on 15/04/2026   INR 53,053.91"\n'
    )
    overlapping_file_bytes = (
        b'"",,Account Statement\n'
        b'"Jharkhand ",,,,Period,From 01/01/2026 To 16/04/2026\n'
        b"Sl. No.,Transaction Date,Value Date,Description,"
        b"Chq / Ref No.,Debit,Credit,Balance,Dr / Cr\n"
        b"1,03-04-2026 19:40:46,03-04-2026,"
        b"UPI/CAFE BREWSOME P/627219443204/resolve interna,"
        b'UPI-609393884269,310.78,,"39,591.75",CR\n'
        b"2,04-04-2026 11:00:00,04-04-2026,"
        b"UPI/NEW COFFEE SHOP/111111111111/UPI,"
        b'UPI-609400000000,125.00,,"52,928.91",CR\n'
        b'Closing balance,"as on 16/04/2026   INR 52,928.91"\n'
    )

    first_response = client.post(
        "/imports/csv",
        data={"bank_name": "kotak", "account_id": "travel-fund"},
        files={"file": ("kotak_statement_1.csv", first_file_bytes, "text/csv")},
    )
    second_response = client.post(
        "/imports/csv",
        data={"bank_name": "kotak", "account_id": "travel-fund"},
        files={"file": ("kotak_statement_2.csv", overlapping_file_bytes, "text/csv")},
    )

    assert first_response.status_code == 201
    assert second_response.status_code == 201
    second_payload = second_response.json()

    assert second_payload["duplicate_file"] is False
    assert second_payload["status"] == "PASS_WITH_WARNINGS"
    assert second_payload["transactions_imported"] == 1
    assert second_payload["duplicate_transactions_detected"] == 1
    assert second_payload["exact_duplicate_transactions"] == 1
    assert second_payload["probable_duplicate_transactions"] == 0
    assert second_payload["ambiguous_transactions_detected"] == 0
    assert second_payload["message"] == (
        "File parsed and 1 new transactions were imported into the canonical ledger "
        "with duplicate warnings."
    )

    with duckdb.connect(str(settings.database_path), read_only=True) as connection:
        canonical_count = connection.execute(
            "SELECT COUNT(*) FROM canonical_transactions WHERE account_id = ?",
            ["travel-fund"],
        ).fetchone()
        second_file_transactions = connection.execute(
            """
            SELECT description_raw, duplicate_confidence
            FROM canonical_transactions
            WHERE source_file_id = ?
            ORDER BY source_row_number
            """,
            [second_payload["file_id"]],
        ).fetchall()

    assert canonical_count == (3,)
    assert second_file_transactions == [
        ("UPI/NEW COFFEE SHOP/111111111111/UPI", "UNIQUE"),
    ]
