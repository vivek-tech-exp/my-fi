"""HDFC parser implementation for canonical transaction mapping."""

from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from app.models.imports import BankName
from app.models.ledger import CanonicalTransactionRecord, TransactionDirection
from app.models.parsing import ParserInspectionResult, RawRowRecord, RawRowType
from app.parsers.base import BaseCsvParser, RowClassification, normalized_header_token

HDFC_DATE_FORMATS = ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%d/%m/%y")


class HdfcCsvParser(BaseCsvParser):
    """HDFC parser for common debit/credit statement CSV exports."""

    bank_name = BankName.HDFC
    parser_name = "hdfc_csv_parser"
    supports_canonical_mapping = True

    def reset_state(self) -> None:
        self._header_columns: list[str] = []

    def is_header_row(self, columns: list[str]) -> bool:
        tokens = self.normalized_header_tokens(columns)
        has_date = any(token in tokens for token in {"date", "transaction date"})
        has_description = any(token in tokens for token in {"narration", "description"})
        has_balance = any(token in tokens for token in {"balance", "closing balance"})
        has_amounts = (
            {"debit", "credit"} <= tokens
            or {"withdrawal amt", "deposit amt"} <= tokens
            or {"withdrawal", "deposit"} <= tokens
        )
        header_detected = has_date and has_description and has_balance and has_amounts
        if header_detected:
            self._header_columns = columns

        return header_detected

    def classify_row(
        self,
        *,
        row_number: int,
        raw_text: str,
        columns: list[str],
        header_columns: list[str] | None,
        inspection_result: ParserInspectionResult,
    ) -> RowClassification:
        base_classification = super().classify_row(
            row_number=row_number,
            raw_text=raw_text,
            columns=columns,
            header_columns=header_columns,
            inspection_result=inspection_result,
        )
        if base_classification.row_type != RawRowType.ACCEPTED:
            return base_classification

        if self._transaction_date(columns) is None:
            return RowClassification(
                row_type=RawRowType.SUSPICIOUS,
                rejection_reason="invalid_transaction_date",
            )

        if not self._description(columns):
            return RowClassification(
                row_type=RawRowType.SUSPICIOUS,
                rejection_reason="missing_description",
            )

        debit_amount = self._debit_amount(columns)
        credit_amount = self._credit_amount(columns)
        if debit_amount is None and credit_amount is None:
            return RowClassification(
                row_type=RawRowType.SUSPICIOUS,
                rejection_reason="invalid_amount_shape",
            )

        if debit_amount is not None and credit_amount is not None:
            return RowClassification(
                row_type=RawRowType.SUSPICIOUS,
                rejection_reason="invalid_amount_shape",
            )

        return RowClassification(row_type=RawRowType.ACCEPTED)

    def map_row_to_canonical_transaction(
        self,
        *,
        row: RawRowRecord,
        account_id: str | None,
    ) -> CanonicalTransactionRecord | None:
        if row.raw_payload is None:
            return None

        transaction_date = self._transaction_date(row.raw_payload)
        description_raw = self._description(row.raw_payload)
        debit_amount = self._debit_amount(row.raw_payload)
        credit_amount = self._credit_amount(row.raw_payload)
        if transaction_date is None or not description_raw:
            return None

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
            value_date=self._value_date(row.raw_payload),
            description_raw=description_raw,
            amount=amount,
            direction=direction,
            balance=self._balance(row.raw_payload),
            source_row_number=row.row_number,
            reference_number=self._reference_number(row.raw_payload),
        )

    def _transaction_date(self, columns: list[str]) -> date | None:
        return self._parse_date(
            self._column_value(columns, {"date", "transaction date"}, default_index=0)
        )

    def _value_date(self, columns: list[str]) -> date | None:
        return self._parse_date(
            self._column_value(columns, {"value date", "value dt"}, default_index=None)
        )

    def _description(self, columns: list[str]) -> str:
        return self._column_value(
            columns,
            {"narration", "description"},
            default_index=1,
        ).strip()

    def _reference_number(self, columns: list[str]) -> str | None:
        reference_number = self._column_value(
            columns,
            {"chq ref no", "cheque ref no", "ref no", "reference number"},
            default_index=2 if len(columns) >= 7 else None,
        ).strip()
        return reference_number or None

    def _debit_amount(self, columns: list[str]) -> Decimal | None:
        return self._parse_decimal(
            self._column_value(
                columns,
                {"debit", "withdrawal", "withdrawal amt"},
                default_index=4 if len(columns) >= 7 else 2,
            )
        )

    def _credit_amount(self, columns: list[str]) -> Decimal | None:
        return self._parse_decimal(
            self._column_value(
                columns,
                {"credit", "deposit", "deposit amt"},
                default_index=5 if len(columns) >= 7 else 3,
            )
        )

    def _balance(self, columns: list[str]) -> Decimal | None:
        return self._parse_decimal(
            self._column_value(
                columns,
                {"balance", "closing balance"},
                default_index=6 if len(columns) >= 7 else 4,
            )
        )

    def _column_value(
        self,
        columns: list[str],
        accepted_tokens: set[str],
        *,
        default_index: int | None,
    ) -> str:
        for index, header in enumerate(self._header_columns):
            if index < len(columns) and normalized_header_token(header) in accepted_tokens:
                return columns[index]

        if default_index is not None and default_index < len(columns):
            return columns[default_index]

        return ""

    def _parse_date(self, raw_value: str) -> date | None:
        stripped_value = raw_value.strip()
        if not stripped_value:
            return None

        for date_format in HDFC_DATE_FORMATS:
            try:
                return datetime.strptime(stripped_value, date_format).date()
            except ValueError:
                continue

        return None

    def _parse_decimal(self, raw_value: str) -> Decimal | None:
        stripped_value = raw_value.strip().replace(",", "")
        if not stripped_value:
            return None

        try:
            return Decimal(stripped_value)
        except InvalidOperation:
            return None
