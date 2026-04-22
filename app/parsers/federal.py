"""Federal parser implementation for canonical transaction mapping."""

from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from app.models.imports import BankName
from app.models.ledger import CanonicalTransactionRecord, TransactionDirection
from app.models.parsing import ParserInspectionResult, RawRowRecord, RawRowType
from app.parsers.base import BaseCsvParser, RowClassification, normalized_header_token

FEDERAL_DATE_FORMATS = ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%d/%m/%y")


class FederalCsvParser(BaseCsvParser):
    """Federal parser for common debit/credit statement CSV exports."""

    bank_name = BankName.FEDERAL
    parser_name = "federal_csv_parser"
    supports_canonical_mapping = True

    def is_header_row(self, columns: list[str]) -> bool:
        tokens = self.normalized_header_tokens(columns)
        has_date = any(
            token in tokens for token in {"tran date", "transaction date", "value date", "date"}
        )
        has_description = any(token in tokens for token in {"particulars", "narration"})
        has_balance = "balance" in tokens
        has_amounts = (
            {"withdrawals", "deposits"} <= tokens
            or {"withdrawal", "deposit"} <= tokens
            or {"debit", "credit"} <= tokens
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
        base_classification = super().classify_row(
            row_number=row_number,
            raw_text=raw_text,
            columns=columns,
            header_columns=header_columns,
            inspection_result=inspection_result,
        )
        if base_classification.row_type != RawRowType.ACCEPTED:
            return base_classification

        if self._transaction_date(columns, header_columns=header_columns) is None:
            return RowClassification(
                row_type=RawRowType.SUSPICIOUS,
                rejection_reason="invalid_transaction_date",
            )

        if not self._description(columns, header_columns=header_columns):
            return RowClassification(
                row_type=RawRowType.SUSPICIOUS,
                rejection_reason="missing_description",
            )

        debit_amount = self._debit_amount(columns, header_columns=header_columns)
        credit_amount = self._credit_amount(columns, header_columns=header_columns)
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

    def _transaction_date(
        self,
        columns: list[str],
        *,
        header_columns: list[str] | None = None,
    ) -> date | None:
        return self._parse_date(
            self._column_value(
                columns,
                {"tran date", "transaction date", "date"},
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
                {"value date"},
                default_index=2 if len(columns) >= 7 else None,
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
            {"particulars", "narration", "description"},
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
            {"ref no", "reference number", "cheque number"},
            default_index=6 if len(columns) >= 7 else None,
            header_columns=header_columns,
        ).strip()
        return reference_number or None

    def _debit_amount(
        self,
        columns: list[str],
        *,
        header_columns: list[str] | None = None,
    ) -> Decimal | None:
        return self._parse_decimal(
            self._column_value(
                columns,
                {"withdrawals", "withdrawal", "debit"},
                default_index=3 if len(columns) >= 7 else 2,
                header_columns=header_columns,
            )
        )

    def _credit_amount(
        self,
        columns: list[str],
        *,
        header_columns: list[str] | None = None,
    ) -> Decimal | None:
        return self._parse_decimal(
            self._column_value(
                columns,
                {"deposits", "deposit", "credit"},
                default_index=4 if len(columns) >= 7 else 3,
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
                {"balance"},
                default_index=5 if len(columns) >= 7 else 4,
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

    def _parse_date(self, raw_value: str) -> date | None:
        stripped_value = raw_value.strip()
        if not stripped_value:
            return None

        for date_format in FEDERAL_DATE_FORMATS:
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
