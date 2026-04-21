"""Tests for parser selection and bank-specific header inspection."""

from decimal import Decimal
from uuid import uuid4

from app.models.imports import BankName
from app.models.parsing import RawRowRecord, RawRowType
from app.parsers import get_bank_parser
from app.parsers.base import BaseCsvParser, RowRepairOutcome


class RepairingTestParser(BaseCsvParser):
    bank_name = BankName.HDFC
    parser_name = "repairing_test_parser"

    def is_header_row(self, columns: list[str]) -> bool:
        return columns == ["Date", "Narration"]

    def repair_row(
        self,
        *,
        row_number: int,
        raw_text: str,
        columns: list[str],
        header_columns: list[str] | None,
    ) -> RowRepairOutcome:
        if row_number == 3:
            return RowRepairOutcome(
                row_text="2026-04-01,Fixed",
                columns=["2026-04-01", "Fixed"],
                repaired=True,
            )

        return super().repair_row(
            row_number=row_number,
            raw_text=raw_text,
            columns=columns,
            header_columns=header_columns,
        )


def test_hdfc_parser_detects_header_and_accepts_data_rows() -> None:
    parser = get_bank_parser(bank_name=BankName.HDFC, parser_version="v1")
    inspection_result = parser.inspect_text(
        file_id=uuid4(),
        normalized_text=(
            "Date,Narration,Debit,Credit,Balance\n2026-04-01,Salary,,1000.00,1000.00\n"
        ),
        delimiter=",",
        account_id=None,
    )

    assert parser.parser_name == "hdfc_csv_parser"
    assert inspection_result.header_detected is True
    assert inspection_result.raw_rows_recorded == 2
    assert inspection_result.accepted_rows_recorded == 1
    assert inspection_result.ignored_rows_recorded == 1
    assert inspection_result.suspicious_rows_recorded == 0
    assert inspection_result.transactions_imported == 1
    transaction = inspection_result.canonical_transactions[0]
    assert transaction.bank_name == "hdfc"
    assert transaction.amount == Decimal("1000.00")
    assert transaction.direction == "CREDIT"
    assert transaction.balance == Decimal("1000.00")


def test_kotak_parser_extracts_statement_dates_and_canonical_transactions() -> None:
    parser = get_bank_parser(bank_name=BankName.KOTAK, parser_version="v1")
    inspection_result = parser.inspect_text(
        file_id=uuid4(),
        normalized_text=(
            '"",,Account Statement\n'
            '"Jharkhand ",,,,Period,From 01/01/2026 To 15/04/2026\n'
            "Sl. No.,Transaction Date,Value Date,Description,"
            "Chq / Ref No.,Debit,Credit,Balance,Dr / Cr\n"
            "1,03-04-2026 19:40:46,03-04-2026,"
            "UPI/CAFE BREWSOME P/627219443204/resolve interna,"
            'UPI-609393884269,310.78,,"39,591.75",CR\n'
            'Closing balance,"as on 15/04/2026   INR 39,591.75"\n'
        ),
        delimiter=",",
        account_id="travel-fund",
    )

    assert parser.parser_name == "kotak_csv_parser"
    assert inspection_result.header_detected is True
    assert inspection_result.raw_rows_recorded == 5
    assert inspection_result.accepted_rows_recorded == 1
    assert inspection_result.ignored_rows_recorded == 4
    assert inspection_result.suspicious_rows_recorded == 0
    assert inspection_result.statement_start_date is not None
    assert inspection_result.statement_start_date.isoformat() == "2026-01-01"
    assert inspection_result.statement_end_date is not None
    assert inspection_result.statement_end_date.isoformat() == "2026-04-15"
    assert inspection_result.transactions_imported == 1
    transaction = inspection_result.canonical_transactions[0]
    assert transaction.bank_name == "kotak"
    assert transaction.account_id == "travel-fund"
    assert transaction.amount == Decimal("310.78")
    assert transaction.direction == "DEBIT"
    assert transaction.balance == Decimal("39591.75")
    assert transaction.source_row_number == 4


def test_federal_parser_uses_bank_specific_header_tokens() -> None:
    parser = get_bank_parser(bank_name=BankName.FEDERAL, parser_version="v1")
    inspection_result = parser.inspect_text(
        file_id=uuid4(),
        normalized_text=(
            "Tran Date,Particulars,Withdrawals,Deposits,Balance\n"
            "2026-04-01,Salary,,1000.00,1000.00\n"
        ),
        delimiter=",",
        account_id=None,
    )

    assert parser.parser_name == "federal_csv_parser"
    assert inspection_result.header_detected is True
    assert inspection_result.raw_rows_recorded == 2
    assert inspection_result.accepted_rows_recorded == 1
    assert inspection_result.ignored_rows_recorded == 1
    assert inspection_result.transactions_imported == 1
    transaction = inspection_result.canonical_transactions[0]
    assert transaction.bank_name == "federal"
    assert transaction.amount == Decimal("1000.00")
    assert transaction.direction == "CREDIT"
    assert transaction.balance == Decimal("1000.00")


def test_base_parser_records_blank_repeated_repaired_and_malformed_rows(monkeypatch) -> None:
    parser = RepairingTestParser(parser_version="v1")
    inspection_result = parser.inspect_text(
        file_id=uuid4(),
        normalized_text=("\nDate,Narration\nbroken-row\nDate,Narration\n2026-04-02,Clean\n"),
        delimiter=",",
        account_id=None,
    )

    assert inspection_result.raw_rows_recorded == 5
    assert [row.rejection_reason for row in inspection_result.raw_rows] == [
        "blank_row",
        "header_row",
        None,
        "repeated_header_row",
        None,
    ]
    assert inspection_result.raw_rows[2].repaired_row is True
    assert inspection_result.raw_rows[2].normalized_text == "2026-04-01,Fixed"

    mismatch_result = parser.inspect_text(
        file_id=uuid4(),
        normalized_text="Date,Narration\ntoo,many,columns\n",
        delimiter=",",
        account_id=None,
    )
    assert mismatch_result.raw_rows[1].rejection_reason == "column_count_mismatch"

    raw_row = RawRowRecord(
        raw_row_id=uuid4(),
        file_id=uuid4(),
        row_number=1,
        parser_name=parser.parser_name,
        parser_version=parser.parser_version,
        row_type=RawRowType.ACCEPTED,
        raw_text="raw",
    )
    assert parser.map_row_to_canonical_transaction(row=raw_row, account_id=None) is None

    monkeypatch.setattr("app.parsers.base.reader", lambda *_args, **_kwargs: iter(()))
    assert parser._split_row("raw", ",") == ["raw"]


def test_hdfc_parser_classifies_invalid_rows_and_maps_debits_with_reference_numbers() -> None:
    parser = get_bank_parser(bank_name=BankName.HDFC, parser_version="v1")
    inspection_result = parser.inspect_text(
        file_id=uuid4(),
        normalized_text=(
            "metadata before header\n"
            "Date,Narration,Reference Number,Value Date,Debit,Credit,Balance\n"
            "2026-04-01,Cafe,REF-1,2026-04-01,120.50,,879.50\n"
            "bad-date,Cafe,REF-2,2026-04-01,120.50,,879.50\n"
            "2026-04-02,,REF-3,2026-04-02,120.50,,879.50\n"
            "2026-04-03,Cafe,REF-4,2026-04-03,,,879.50\n"
            "2026-04-04,Cafe,REF-5,2026-04-04,10.00,20.00,879.50\n"
            "2026-04-05,Cafe,REF-6,not-a-date,10.00,,bad-decimal\n"
        ),
        delimiter=",",
        account_id="primary",
    )

    accepted_transactions = inspection_result.canonical_transactions

    assert inspection_result.suspicious_rows_recorded == 5
    assert accepted_transactions[0].direction == "DEBIT"
    assert accepted_transactions[0].amount == Decimal("120.50")
    assert accepted_transactions[0].reference_number == "REF-1"
    assert accepted_transactions[1].value_date is None
    assert accepted_transactions[1].balance is None

    raw_row = RawRowRecord(
        raw_row_id=uuid4(),
        file_id=uuid4(),
        row_number=1,
        parser_name=parser.parser_name,
        parser_version=parser.parser_version,
        row_type=RawRowType.ACCEPTED,
        raw_text="raw",
    )
    assert parser.map_row_to_canonical_transaction(row=raw_row, account_id=None) is None
    assert (
        parser.map_row_to_canonical_transaction(
            row=raw_row.model_copy(
                update={"raw_payload": ["bad-date", "Cafe", "10.00", "", "100.00"]}
            ),
            account_id=None,
        )
        is None
    )
    assert (
        parser.map_row_to_canonical_transaction(
            row=raw_row.model_copy(
                update={
                    "raw_payload": [
                        "2026-04-01",
                        "Cafe",
                        "REF-1",
                        "2026-04-01",
                        "",
                        "",
                        "100.00",
                    ]
                }
            ),
            account_id=None,
        )
        is None
    )
    assert parser._column_value(["fallback"], {"missing"}, default_index=0) == "fallback"


def test_federal_parser_classifies_invalid_rows_and_maps_debits() -> None:
    parser = get_bank_parser(bank_name=BankName.FEDERAL, parser_version="v1")
    inspection_result = parser.inspect_text(
        file_id=uuid4(),
        normalized_text=(
            "metadata before header\n"
            "Tran Date,Particulars,Value Date,Withdrawals,Deposits,Balance,Ref No\n"
            "2026-04-01,Cafe,2026-04-01,120.50,,879.50,REF-1\n"
            "bad-date,Cafe,2026-04-01,120.50,,879.50,REF-2\n"
            "2026-04-02,,2026-04-02,120.50,,879.50,REF-3\n"
            "2026-04-03,Cafe,2026-04-03,,,879.50,REF-4\n"
            "2026-04-04,Cafe,2026-04-04,10.00,20.00,879.50,REF-5\n"
            "2026-04-05,Cafe,not-a-date,10.00,,bad-decimal,\n"
        ),
        delimiter=",",
        account_id="primary",
    )

    accepted_transactions = inspection_result.canonical_transactions

    assert inspection_result.suspicious_rows_recorded == 5
    assert accepted_transactions[0].direction == "DEBIT"
    assert accepted_transactions[0].amount == Decimal("120.50")
    assert accepted_transactions[0].reference_number == "REF-1"
    assert accepted_transactions[1].value_date is None
    assert accepted_transactions[1].balance is None

    raw_row = RawRowRecord(
        raw_row_id=uuid4(),
        file_id=uuid4(),
        row_number=1,
        parser_name=parser.parser_name,
        parser_version=parser.parser_version,
        row_type=RawRowType.ACCEPTED,
        raw_text="raw",
    )
    assert parser.map_row_to_canonical_transaction(row=raw_row, account_id=None) is None
    assert (
        parser.map_row_to_canonical_transaction(
            row=raw_row.model_copy(
                update={"raw_payload": ["bad-date", "Cafe", "10.00", "", "100.00"]}
            ),
            account_id=None,
        )
        is None
    )
    assert (
        parser.map_row_to_canonical_transaction(
            row=raw_row.model_copy(
                update={
                    "raw_payload": [
                        "2026-04-01",
                        "Cafe",
                        "2026-04-01",
                        "",
                        "",
                        "100.00",
                        "REF-1",
                    ]
                }
            ),
            account_id=None,
        )
        is None
    )
    assert parser._column_value(["fallback"], {"missing"}, default_index=0) == "fallback"


def test_kotak_parser_classifies_metadata_footer_and_malformed_rows() -> None:
    parser = get_bank_parser(bank_name=BankName.KOTAK, parser_version="v1")
    inspection_result = parser.inspect_text(
        file_id=uuid4(),
        normalized_text=(
            "\n"
            '""\n'
            "Unexpected content before header\n"
            ",,,\n"
            "Sl. No.,Transaction Date,Value Date,Description,"
            "Chq / Ref No.,Debit,Credit,Balance,Dr / Cr\n"
            "1,not-a-date,03-04-2026,Cafe,REF-1,120.50,,879.50,CR\n"
            "2,03-04-2026 10:00:00,03-04-2026,Cafe,REF-2,,,879.50,CR\n"
            "3,03-04-2026 10:00:00,03-04-2026,Cafe,REF-3,10.00,20.00,879.50,CR\n"
            "4,03-04-2026 10:00:00,03-04-2026,Cafe,REF-4,,20.00,879.50,DR\n"
            "5,03-04-2026 10:00:00,03-04-2026,Cafe,REF-5,,20.00,,\n"
            "Closing balance,as on\n"
            "Customer Contact Centre\n"
            "Write to us at Customer Contact Centre\n"
            "too,few,columns\n"
        ),
        delimiter=",",
        account_id="primary",
    )

    transactions = inspection_result.canonical_transactions

    assert inspection_result.ignored_rows_recorded == 7
    assert inspection_result.suspicious_rows_recorded == 5
    assert transactions[0].direction == "CREDIT"
    assert transactions[0].balance == Decimal("-879.50")
    assert transactions[1].balance is None

    raw_row = RawRowRecord(
        raw_row_id=uuid4(),
        file_id=uuid4(),
        row_number=1,
        parser_name=parser.parser_name,
        parser_version=parser.parser_version,
        row_type=RawRowType.ACCEPTED,
        raw_text="raw",
        raw_payload=["too", "short"],
    )
    assert parser.map_row_to_canonical_transaction(row=raw_row, account_id=None) is None
    assert (
        parser.map_row_to_canonical_transaction(
            row=raw_row.model_copy(
                update={
                    "raw_payload": [
                        "1",
                        "03-04-2026 10:00:00",
                        "03-04-2026",
                        "Cafe",
                        "REF-1",
                        "",
                        "",
                        "879.50",
                        "XX",
                    ]
                }
            ),
            account_id=None,
        )
        is None
    )
    assert parser._parse_decimal("not-a-decimal") is None
    assert parser._parse_balance("879.50", "XX") == Decimal("879.50")
