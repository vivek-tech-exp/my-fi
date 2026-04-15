"""Base classes and helpers for bank CSV parser inspection."""

from __future__ import annotations

from abc import ABC, abstractmethod
from csv import Error as CsvError
from csv import reader
from dataclasses import dataclass
from re import sub
from uuid import UUID, uuid4

from app.models.imports import BankName
from app.models.parsing import ParserInspectionResult, RawRowRecord, RawRowType


@dataclass(frozen=True)
class RowRepairOutcome:
    """Normalized row content after optional parser repair logic."""

    row_text: str
    columns: list[str]
    repaired: bool = False


@dataclass(frozen=True)
class RowClassification:
    """Classification result for a parsed row."""

    row_type: RawRowType
    rejection_reason: str | None = None


class BaseCsvParser(ABC):
    """Header-aware inspection framework shared by bank-specific parsers."""

    bank_name: BankName
    parser_name: str

    def __init__(self, *, parser_version: str) -> None:
        self.parser_version = parser_version

    def inspect_text(
        self,
        *,
        file_id: UUID,
        normalized_text: str,
        delimiter: str | None,
    ) -> ParserInspectionResult:
        """Inspect normalized CSV text and emit raw-row audit records."""

        inspection_result = ParserInspectionResult(
            parser_name=self.parser_name,
            parser_version=self.parser_version,
        )
        header_columns: list[str] | None = None
        effective_delimiter = delimiter or ","

        for row_number, raw_line in enumerate(normalized_text.splitlines(), start=1):
            if self.should_ignore_line(raw_line):
                inspection_result.add_row(
                    self._build_raw_row(
                        file_id=file_id,
                        row_number=row_number,
                        row_type=RawRowType.IGNORED,
                        raw_text=raw_line,
                        normalized_text=None,
                        raw_payload=None,
                        rejection_reason="blank_row",
                        header_row=False,
                        repaired_row=False,
                    )
                )
                continue

            columns = self._split_row(raw_line, effective_delimiter)
            repair_outcome = self.repair_row(
                row_number=row_number,
                raw_text=raw_line,
                columns=columns,
                header_columns=header_columns,
            )

            if self.is_header_row(repair_outcome.columns):
                row_reason = "header_row" if header_columns is None else "repeated_header_row"
                if header_columns is None:
                    header_columns = repair_outcome.columns

                inspection_result.add_row(
                    self._build_raw_row(
                        file_id=file_id,
                        row_number=row_number,
                        row_type=RawRowType.IGNORED,
                        raw_text=raw_line,
                        normalized_text=(
                            repair_outcome.row_text if repair_outcome.repaired else None
                        ),
                        raw_payload=repair_outcome.columns,
                        rejection_reason=row_reason,
                        header_row=True,
                        repaired_row=repair_outcome.repaired,
                    )
                )
                continue

            classification = self.classify_row(
                row_number=row_number,
                raw_text=repair_outcome.row_text,
                columns=repair_outcome.columns,
                header_columns=header_columns,
            )
            inspection_result.add_row(
                self._build_raw_row(
                    file_id=file_id,
                    row_number=row_number,
                    row_type=classification.row_type,
                    raw_text=raw_line,
                    normalized_text=repair_outcome.row_text if repair_outcome.repaired else None,
                    raw_payload=repair_outcome.columns,
                    rejection_reason=classification.rejection_reason,
                    header_row=False,
                    repaired_row=repair_outcome.repaired,
                )
            )

        return inspection_result

    def should_ignore_line(self, raw_text: str) -> bool:
        """Skip rows that should not reach the parser-specific hooks."""

        return not raw_text.strip()

    def repair_row(
        self,
        *,
        row_number: int,
        raw_text: str,
        columns: list[str],
        header_columns: list[str] | None,
    ) -> RowRepairOutcome:
        """Give bank parsers a place to repair malformed rows before classification."""

        del row_number, header_columns
        return RowRepairOutcome(row_text=raw_text, columns=columns, repaired=False)

    @abstractmethod
    def is_header_row(self, columns: list[str]) -> bool:
        """Return True when the provided columns represent a bank header row."""

    def classify_row(
        self,
        *,
        row_number: int,
        raw_text: str,
        columns: list[str],
        header_columns: list[str] | None,
    ) -> RowClassification:
        """Classify a parsed row when the bank parser has not yet mapped it canonically."""

        del row_number, raw_text

        if header_columns is None:
            return RowClassification(
                row_type=RawRowType.SUSPICIOUS,
                rejection_reason="content_before_header",
            )

        if len(columns) != len(header_columns):
            return RowClassification(
                row_type=RawRowType.SUSPICIOUS,
                rejection_reason="column_count_mismatch",
            )

        return RowClassification(row_type=RawRowType.ACCEPTED)

    def map_row_to_canonical_transaction(self, row: RawRowRecord) -> None:
        """Placeholder hook for the later canonical-mapping milestone."""

        del row
        return None

    def normalized_header_tokens(self, columns: list[str]) -> set[str]:
        """Normalize header cells into stable tokens for bank-specific matching."""

        return {
            normalized_header_token(column) for column in columns if normalized_header_token(column)
        }

    def _build_raw_row(
        self,
        *,
        file_id: UUID,
        row_number: int,
        row_type: RawRowType,
        raw_text: str,
        normalized_text: str | None,
        raw_payload: list[str] | None,
        rejection_reason: str | None,
        header_row: bool,
        repaired_row: bool,
    ) -> RawRowRecord:
        return RawRowRecord(
            raw_row_id=uuid4(),
            file_id=file_id,
            row_number=row_number,
            parser_name=self.parser_name,
            parser_version=self.parser_version,
            row_type=row_type,
            raw_text=raw_text,
            normalized_text=normalized_text,
            raw_payload=raw_payload,
            rejection_reason=rejection_reason,
            header_row=header_row,
            repaired_row=repaired_row,
        )

    def _split_row(self, raw_text: str, delimiter: str) -> list[str]:
        try:
            return next(reader([raw_text], delimiter=delimiter))
        except (CsvError, StopIteration):
            return [raw_text]


def normalized_header_token(value: str) -> str:
    """Canonicalize a header cell so bank-specific matching is stable."""

    collapsed = sub(r"\s+", " ", sub(r"[^a-z0-9]+", " ", value.casefold())).strip()
    return collapsed
