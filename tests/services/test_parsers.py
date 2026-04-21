"""Tests for parser selection and bank-specific header inspection."""

from decimal import Decimal
from uuid import uuid4

from app.models.imports import BankName
from app.parsers import get_bank_parser


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
