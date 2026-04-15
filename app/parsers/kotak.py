"""Kotak parser scaffolding for raw-row inspection."""

from app.models.imports import BankName
from app.parsers.base import BaseCsvParser


class KotakCsvParser(BaseCsvParser):
    """Lightweight Kotak parser until canonical transaction mapping lands."""

    bank_name = BankName.KOTAK
    parser_name = "kotak_csv_parser"

    def is_header_row(self, columns: list[str]) -> bool:
        tokens = self.normalized_header_tokens(columns)
        has_date = any(token in tokens for token in {"date", "transaction date"})
        has_description = any(token in tokens for token in {"narration", "description"})
        has_balance = "balance" in tokens
        has_amounts = (
            {"withdrawal dr", "deposit cr"} <= tokens
            or {"debit", "credit"} <= tokens
            or {"withdrawal", "deposit"} <= tokens
        )
        return has_date and has_description and has_balance and has_amounts
