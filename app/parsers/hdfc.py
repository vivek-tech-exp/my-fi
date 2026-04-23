"""HDFC parser implementation for canonical transaction mapping."""

from csv import writer
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from io import StringIO

from app.models.imports import BankName
from app.models.ledger import CanonicalTransactionRecord, TransactionDirection
from app.models.parsing import ParserInspectionResult, RawRowRecord, RawRowType
from app.parsers.base import (
    BaseCsvParser,
    RowClassification,
    RowRepairOutcome,
    normalized_header_token,
)

HDFC_DATE_FORMATS = ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%d/%m/%y")
HDFC_DEBIT_TOKENS = {"debit", "debit amount", "withdrawal", "withdrawal amt"}
HDFC_CREDIT_TOKENS = {"credit", "credit amount", "deposit", "deposit amt"}
HDFC_VALUE_DATE_TOKENS = {"value date", "value dat", "value dt"}
HDFC_REFERENCE_TOKENS = {
    "chq ref no",
    "chq ref number",
    "cheque ref no",
    "ref no",
    "reference number",
}


class HdfcCsvParser(BaseCsvParser):
    """HDFC parser for common debit/credit statement CSV exports."""

    bank_name = BankName.HDFC
    parser_name = "hdfc_csv_parser"
    supports_canonical_mapping = True

    def is_header_row(self, columns: list[str]) -> bool:
        tokens = self.normalized_header_tokens(columns)
        has_date = any(token in tokens for token in {"date", "transaction date"})
        has_description = any(token in tokens for token in {"narration", "description"})
        has_balance = any(token in tokens for token in {"balance", "closing balance"})
        has_amounts = bool(tokens & HDFC_DEBIT_TOKENS) and bool(tokens & HDFC_CREDIT_TOKENS)
        return has_date and has_description and has_balance and has_amounts

    def repair_row(
        self,
        *,
        row_number: int,
        raw_text: str,
        columns: list[str],
        header_columns: list[str] | None,
    ) -> RowRepairOutcome:
        if header_columns is None or self.is_header_row(columns):
            return super().repair_row(
                row_number=row_number,
                raw_text=raw_text,
                columns=columns,
                header_columns=header_columns,
            )

        repaired_columns = self._repair_split_narration_columns(columns, header_columns)
        if repaired_columns is None:
            normalized_columns = self._normalize_seven_column_order(columns, header_columns)
            return RowRepairOutcome(
                row_text=raw_text,
                columns=normalized_columns or columns,
                repaired=False,
            )

        normalized_columns = (
            self._normalize_seven_column_order(repaired_columns, header_columns) or repaired_columns
        )
        return RowRepairOutcome(
            row_text=self._to_csv_line(normalized_columns),
            columns=normalized_columns,
            repaired=True,
        )

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
            amount = abs(debit_amount)
            direction = (
                TransactionDirection.CREDIT if debit_amount < 0 else TransactionDirection.DEBIT
            )
        elif credit_amount is not None:
            amount = abs(credit_amount)
            direction = (
                TransactionDirection.DEBIT if credit_amount < 0 else TransactionDirection.CREDIT
            )
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

    def _transaction_date(
        self,
        columns: list[str],
        *,
        header_columns: list[str] | None = None,
    ) -> date | None:
        return self._parse_date(
            self._column_value(
                columns,
                {"date", "transaction date"},
                default_index=0,
                header_columns=header_columns,
            )
        )

    def _value_date(
        self,
        columns: list[str],
        *,
        header_columns: list[str] | None = None,
    ) -> date | None:
        return self._parse_date(
            self._column_value(
                columns,
                HDFC_VALUE_DATE_TOKENS,
                default_index=3 if len(columns) >= 7 else None,
                header_columns=header_columns,
            )
        )

    def _description(
        self,
        columns: list[str],
        *,
        header_columns: list[str] | None = None,
    ) -> str:
        return self._column_value(
            columns,
            {"narration", "description"},
            default_index=1,
            header_columns=header_columns,
        ).strip()

    def _reference_number(
        self,
        columns: list[str],
        *,
        header_columns: list[str] | None = None,
    ) -> str | None:
        reference_number = self._column_value(
            columns,
            HDFC_REFERENCE_TOKENS,
            default_index=2 if len(columns) >= 7 else None,
            header_columns=header_columns,
        ).strip()
        return reference_number or None

    def _debit_amount(
        self,
        columns: list[str],
        *,
        header_columns: list[str] | None = None,
    ) -> Decimal | None:
        return self._parse_transaction_amount(
            self._column_value(
                columns,
                HDFC_DEBIT_TOKENS,
                default_index=4 if len(columns) >= 7 else 2,
                header_columns=header_columns,
            )
        )

    def _credit_amount(
        self,
        columns: list[str],
        *,
        header_columns: list[str] | None = None,
    ) -> Decimal | None:
        return self._parse_transaction_amount(
            self._column_value(
                columns,
                HDFC_CREDIT_TOKENS,
                default_index=5 if len(columns) >= 7 else 3,
                header_columns=header_columns,
            )
        )

    def _balance(
        self,
        columns: list[str],
        *,
        header_columns: list[str] | None = None,
    ) -> Decimal | None:
        return self._parse_decimal(
            self._column_value(
                columns,
                {"balance", "closing balance"},
                default_index=6 if len(columns) >= 7 else 4,
                header_columns=header_columns,
            )
        )

    def _column_value(
        self,
        columns: list[str],
        accepted_tokens: set[str],
        *,
        default_index: int | None,
        header_columns: list[str] | None = None,
    ) -> str:
        for index, header in enumerate(header_columns or []):
            if index < len(columns) and normalized_header_token(header) in accepted_tokens:
                return columns[index]

        if default_index is not None and default_index < len(columns):
            return columns[default_index]

        return ""

    def _normalize_seven_column_order(
        self,
        columns: list[str],
        header_columns: list[str],
    ) -> list[str] | None:
        if len(columns) != 7 or len(header_columns) != 7:
            return None

        return [
            self._column_value(
                columns,
                {"date", "transaction date"},
                default_index=None,
                header_columns=header_columns,
            ),
            self._column_value(
                columns,
                {"narration", "description"},
                default_index=None,
                header_columns=header_columns,
            ),
            self._column_value(
                columns,
                HDFC_REFERENCE_TOKENS,
                default_index=None,
                header_columns=header_columns,
            ),
            self._column_value(
                columns,
                HDFC_VALUE_DATE_TOKENS,
                default_index=None,
                header_columns=header_columns,
            ),
            self._column_value(
                columns,
                HDFC_DEBIT_TOKENS,
                default_index=None,
                header_columns=header_columns,
            ),
            self._column_value(
                columns,
                HDFC_CREDIT_TOKENS,
                default_index=None,
                header_columns=header_columns,
            ),
            self._column_value(
                columns,
                {"balance", "closing balance"},
                default_index=None,
                header_columns=header_columns,
            ),
        ]

    def _repair_split_narration_columns(
        self,
        columns: list[str],
        header_columns: list[str] | None,
    ) -> list[str] | None:
        if header_columns is None:
            return None

        expected_count = len(header_columns)
        if len(columns) <= expected_count:
            return None

        extra_columns = len(columns) - expected_count
        if extra_columns not in {1, 2}:
            return None

        narration_index = self._narration_column_index(header_columns)
        if narration_index is None:
            return None

        merge_stop = narration_index + extra_columns + 1
        merged_narration = ",".join(part.strip() for part in columns[narration_index:merge_stop])
        repaired_columns = columns[:narration_index] + [merged_narration] + columns[merge_stop:]

        debit_amount = self._debit_amount(repaired_columns, header_columns=header_columns)
        credit_amount = self._credit_amount(repaired_columns, header_columns=header_columns)
        if debit_amount is None and credit_amount is None:
            return None

        if debit_amount is not None and credit_amount is not None:
            return None

        return repaired_columns

    def _narration_column_index(self, header_columns: list[str]) -> int | None:
        for index, header in enumerate(header_columns):
            token = normalized_header_token(header)
            if token in {"narration", "description"}:
                return index

        return None

    def _to_csv_line(self, columns: list[str]) -> str:
        buffer = StringIO()
        csv_writer = writer(buffer)
        csv_writer.writerow(columns)
        return buffer.getvalue().rstrip("\r\n")

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

    def _parse_transaction_amount(self, raw_value: str) -> Decimal | None:
        amount = self._parse_decimal(raw_value)
        if amount is None or amount == Decimal("0"):
            return None

        return amount
