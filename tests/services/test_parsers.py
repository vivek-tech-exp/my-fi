"""Tests for parser selection and bank-specific header inspection."""

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
    )

    assert parser.parser_name == "hdfc_csv_parser"
    assert inspection_result.header_detected is True
    assert inspection_result.raw_rows_recorded == 2
    assert inspection_result.accepted_rows_recorded == 1
    assert inspection_result.ignored_rows_recorded == 1
    assert inspection_result.suspicious_rows_recorded == 0


def test_kotak_parser_uses_bank_specific_header_tokens() -> None:
    parser = get_bank_parser(bank_name=BankName.KOTAK, parser_version="v1")
    inspection_result = parser.inspect_text(
        file_id=uuid4(),
        normalized_text=(
            "Date,Narration,Withdrawal (Dr),Deposit (Cr),Balance\n"
            "2026-04-01,Salary,,1000.00,1000.00\n"
        ),
        delimiter=",",
    )

    assert parser.parser_name == "kotak_csv_parser"
    assert inspection_result.header_detected is True
    assert inspection_result.raw_rows_recorded == 2
    assert inspection_result.accepted_rows_recorded == 1
    assert inspection_result.ignored_rows_recorded == 1


def test_federal_parser_uses_bank_specific_header_tokens() -> None:
    parser = get_bank_parser(bank_name=BankName.FEDERAL, parser_version="v1")
    inspection_result = parser.inspect_text(
        file_id=uuid4(),
        normalized_text=(
            "Tran Date,Particulars,Withdrawals,Deposits,Balance\n"
            "2026-04-01,Salary,,1000.00,1000.00\n"
        ),
        delimiter=",",
    )

    assert parser.parser_name == "federal_csv_parser"
    assert inspection_result.header_detected is True
    assert inspection_result.raw_rows_recorded == 2
    assert inspection_result.accepted_rows_recorded == 1
    assert inspection_result.ignored_rows_recorded == 1
