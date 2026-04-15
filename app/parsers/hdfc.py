"""HDFC parser scaffolding for raw-row inspection."""

from app.models.imports import BankName
from app.parsers.base import BaseCsvParser


class HdfcCsvParser(BaseCsvParser):
    """Lightweight HDFC parser until canonical transaction mapping lands."""

    bank_name = BankName.HDFC
    parser_name = "hdfc_csv_parser"

    def is_header_row(self, columns: list[str]) -> bool:
        tokens = self.normalized_header_tokens(columns)
        has_date = "date" in tokens
        has_description = any(token in tokens for token in {"narration", "description"})
        has_balance = any(token in tokens for token in {"balance", "closing balance"})
        has_amounts = (
            {"debit", "credit"} <= tokens
            or {"withdrawal amt", "deposit amt"} <= tokens
            or {"withdrawal", "deposit"} <= tokens
        )
        return has_date and has_description and has_balance and has_amounts
