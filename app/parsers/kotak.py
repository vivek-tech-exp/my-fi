"""Kotak parser implementation for canonical transaction mapping."""

from datetime import date, datetime
from decimal import Decimal
from re import Match, search

from app.models.imports import BankName
from app.models.ledger import CanonicalTransactionRecord, TransactionDirection
from app.models.parsing import ParserInspectionResult, RawRowRecord, RawRowType
from app.parsers.base import BaseCsvParser, RowClassification

KOTAK_TRANSACTION_DATE_FORMAT = "%d-%m-%Y %H:%M:%S"
KOTAK_VALUE_DATE_FORMAT = "%d-%m-%Y"


class KotakCsvParser(BaseCsvParser):
    """Kotak parser with footer filtering and canonical transaction mapping."""

    bank_name = BankName.KOTAK
    parser_name = "kotak_csv_parser"
    supports_canonical_mapping = True

    def reset_state(self) -> None:
        self._statement_start_date: date | None = None
        self._statement_end_date: date | None = None

    def is_header_row(self, columns: list[str]) -> bool:
        tokens = self.normalized_header_tokens(columns)
        has_date = any(token in tokens for token in {"date", "transaction date", "value date"})
        has_description = any(token in tokens for token in {"narration", "description"})
        has_balance = "balance" in tokens
        has_amounts = {"debit", "credit"} <= tokens
        return has_date and has_description and has_balance and has_amounts

    def classify_row(
        self,
        *,
        row_number: int,
        raw_text: str,
        columns: list[str],
        header_columns: list[str] | None,
        inspection_result: ParserInspectionResult,
    ) -> RowClassification:
        del row_number, inspection_result

        if header_columns is None:
            metadata_reason = self._classify_preamble_row(raw_text, columns)
            if metadata_reason is not None:
                return RowClassification(
                    row_type=RawRowType.IGNORED,
                    rejection_reason=metadata_reason,
                )

            return RowClassification(
                row_type=RawRowType.SUSPICIOUS,
                rejection_reason="content_before_header",
            )

        if self._is_footer_row(raw_text):
            return RowClassification(
                row_type=RawRowType.IGNORED,
                rejection_reason="statement_footer",
            )

        if len(columns) != len(header_columns):
            return RowClassification(
                row_type=RawRowType.SUSPICIOUS,
                rejection_reason="column_count_mismatch",
            )

        if not self._has_valid_amount_shape(columns):
            return RowClassification(
                row_type=RawRowType.SUSPICIOUS,
                rejection_reason="invalid_amount_shape",
            )

        return RowClassification(row_type=RawRowType.ACCEPTED)

    def finalize_result(self, inspection_result: ParserInspectionResult) -> None:
        inspection_result.statement_start_date = self._statement_start_date
        inspection_result.statement_end_date = self._statement_end_date

    def map_row_to_canonical_transaction(
        self,
        *,
        row: RawRowRecord,
        account_id: str | None,
    ) -> CanonicalTransactionRecord | None:
        if row.raw_payload is None or len(row.raw_payload) != 9:
            return None

        transaction_date = datetime.strptime(
            row.raw_payload[1].strip(),
            KOTAK_TRANSACTION_DATE_FORMAT,
        ).date()
        value_date = datetime.strptime(
            row.raw_payload[2].strip(),
            KOTAK_VALUE_DATE_FORMAT,
        ).date()
        description_raw = row.raw_payload[3].strip()
        reference_number = row.raw_payload[4].strip() or None
        debit_amount = self._parse_decimal(row.raw_payload[5])
        credit_amount = self._parse_decimal(row.raw_payload[6])
        balance = self._parse_balance(row.raw_payload[7], row.raw_payload[8])

        if debit_amount is not None:
            amount = debit_amount
            direction = TransactionDirection.DEBIT
        elif credit_amount is not None:
            amount = credit_amount
            direction = TransactionDirection.CREDIT
        else:
            return None

        return self.build_canonical_transaction(
            source_file_id=row.file_id,
            raw_row_id=row.raw_row_id,
            account_id=account_id,
            transaction_date=transaction_date,
            value_date=value_date,
            description_raw=description_raw,
            amount=amount,
            direction=direction,
            balance=balance,
            source_row_number=row.row_number,
            reference_number=reference_number,
        )

    def _classify_preamble_row(self, raw_text: str, columns: list[str]) -> str | None:
        if raw_text.strip() == '""':
            return "account_metadata"

        if self._extract_statement_period(raw_text) is not None:
            return "statement_metadata"

        if any(column.strip() for column in columns):
            return "account_metadata"

        return None

    def _extract_statement_period(self, raw_text: str) -> Match[str] | None:
        match = search(
            r"From\s+(\d{2}/\d{2}/\d{4})\s+To\s+(\d{2}/\d{2}/\d{4})",
            raw_text,
        )
        if match is None:
            return None

        self._statement_start_date = datetime.strptime(match.group(1), "%d/%m/%Y").date()
        self._statement_end_date = datetime.strptime(match.group(2), "%d/%m/%Y").date()
        return match

    def _is_footer_row(self, raw_text: str) -> bool:
        stripped_text = raw_text.strip()
        if stripped_text.startswith("Closing balance"):
            return True

        if "Customer Contact Centre" in stripped_text:
            return True

        return stripped_text.startswith("Write to us at Customer Contact Centre")

    def _has_valid_amount_shape(self, columns: list[str]) -> bool:
        debit_amount = self._parse_decimal(columns[5])
        credit_amount = self._parse_decimal(columns[6])
        if debit_amount is None and credit_amount is None:
            return False

        return debit_amount is None or credit_amount is None

    def _parse_decimal(self, raw_value: str) -> Decimal | None:
        stripped_value = raw_value.strip().replace(",", "")
        if not stripped_value:
            return None

        return Decimal(stripped_value)

    def _parse_balance(self, raw_balance: str, raw_side: str) -> Decimal | None:
        balance = self._parse_decimal(raw_balance)
        if balance is None:
            return None

        side = raw_side.strip().upper()
        if side == "DR":
            return -abs(balance)

        if side == "CR":
            return abs(balance)

        return balance
