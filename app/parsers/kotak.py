"""Kotak parser implementation for canonical transaction mapping."""

from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from re import Match, search

from app.models.imports import BankName
from app.models.ledger import CanonicalTransactionRecord, TransactionDirection
from app.models.parsing import ParserInspectionResult, RawRowRecord, RawRowType
from app.parsers.base import BaseCsvParser, RowClassification, normalized_header_token

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
        self._detected_account_id: str | None = None

    def is_header_row(self, columns: list[str]) -> bool:
        tokens = self.normalized_header_tokens(columns)
        token_list = [token for column in columns if (token := normalized_header_token(column))]
        has_date = any(token in tokens for token in {"date", "transaction date", "value date"})
        has_description = any(token in tokens for token in {"narration", "description"})
        has_balance = "balance" in tokens
        has_amounts = {"debit", "credit"} <= tokens or (
            "amount" in tokens and token_list.count("dr cr") >= 2
        )
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

        if not self._has_valid_date_shape(columns):
            return RowClassification(
                row_type=RawRowType.SUSPICIOUS,
                rejection_reason="invalid_date_shape",
            )

        if not self._has_valid_amount_shape(columns):
            return RowClassification(
                row_type=RawRowType.SUSPICIOUS,
                rejection_reason="invalid_amount_shape",
            )

        return RowClassification(row_type=RawRowType.ACCEPTED)

    def finalize_result(self, inspection_result: ParserInspectionResult) -> None:
        inspection_result.detected_account_id = self._detected_account_id
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
        amount, direction = self._parse_transaction_amount_and_direction(row.raw_payload)
        balance = self._parse_balance(row.raw_payload[7], row.raw_payload[8])
        if amount is None or direction is None:
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

        self._extract_account_id(columns)
        if any(column.strip() for column in columns):
            return "account_metadata"

        return None

    def _extract_account_id(self, columns: list[str]) -> None:
        for index, column in enumerate(columns[:-1]):
            if self.normalized_header_tokens([column]) == {"account no"}:
                account_id = columns[index + 1].strip()
                if account_id:
                    self._detected_account_id = account_id
                return

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
        if self._uses_single_amount_layout(columns):
            amount, direction = self._parse_transaction_amount_and_direction(columns)
            return amount is not None and direction is not None

        debit_amount = self._parse_decimal(columns[5])
        credit_amount = self._parse_decimal(columns[6])
        if debit_amount is None and credit_amount is None:
            return False

        return debit_amount is None or credit_amount is None

    def _uses_single_amount_layout(self, columns: list[str]) -> bool:
        return columns[6].strip().upper() in {"DR", "CR"}

    def _parse_transaction_amount_and_direction(
        self,
        columns: list[str],
    ) -> tuple[Decimal | None, TransactionDirection | None]:
        if self._uses_single_amount_layout(columns):
            amount = self._parse_decimal(columns[5])
            side = columns[6].strip().upper()
            if side == "DR":
                return amount, TransactionDirection.DEBIT
            return amount, TransactionDirection.CREDIT

        debit_amount = self._parse_decimal(columns[5])
        credit_amount = self._parse_decimal(columns[6])
        if debit_amount is not None:
            return debit_amount, TransactionDirection.DEBIT
        if credit_amount is not None:
            return credit_amount, TransactionDirection.CREDIT
        return None, None

    def _has_valid_date_shape(self, columns: list[str]) -> bool:
        try:
            datetime.strptime(columns[1].strip(), KOTAK_TRANSACTION_DATE_FORMAT)
            datetime.strptime(columns[2].strip(), KOTAK_VALUE_DATE_FORMAT)
        except ValueError:
            return False

        return True

    def _parse_decimal(self, raw_value: str) -> Decimal | None:
        stripped_value = raw_value.strip().replace(",", "")
        if not stripped_value:
            return None

        try:
            return Decimal(stripped_value)
        except InvalidOperation:
            return None

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
