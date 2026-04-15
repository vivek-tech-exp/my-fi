"""Registry for bank-specific parser implementations."""

from app.models.imports import BankName
from app.parsers.base import BaseCsvParser
from app.parsers.federal import FederalCsvParser
from app.parsers.hdfc import HdfcCsvParser
from app.parsers.kotak import KotakCsvParser

PARSER_TYPES: dict[BankName, type[BaseCsvParser]] = {
    BankName.HDFC: HdfcCsvParser,
    BankName.KOTAK: KotakCsvParser,
    BankName.FEDERAL: FederalCsvParser,
}


def get_bank_parser(*, bank_name: BankName, parser_version: str) -> BaseCsvParser:
    """Return the parser implementation registered for the given bank."""

    parser_type = PARSER_TYPES[bank_name]
    return parser_type(parser_version=parser_version)
