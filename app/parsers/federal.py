"""Federal parser scaffolding for raw-row inspection."""

from app.models.imports import BankName
from app.parsers.base import BaseCsvParser


class FederalCsvParser(BaseCsvParser):
    """Lightweight Federal parser until canonical transaction mapping lands."""

    bank_name = BankName.FEDERAL
    parser_name = "federal_csv_parser"

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
