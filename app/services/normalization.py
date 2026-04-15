import csv
from collections.abc import Iterable

from app.models.imports import PreParseNormalizationResult

SUPPORTED_DELIMITERS = (",", ";", "\t", "|")


def normalize_uploaded_csv(file_bytes: bytes) -> PreParseNormalizationResult:
    """Decode and normalize raw CSV bytes before parser-specific processing."""

    encoding_detected = _detect_encoding(file_bytes)
    if encoding_detected is None:
        return PreParseNormalizationResult(
            quarantine_required=True,
            failure_reason="Unable to decode the uploaded file with the supported encodings.",
        )

    try:
        decoded_text = file_bytes.decode(encoding_detected)
    except UnicodeDecodeError:
        return PreParseNormalizationResult(
            quarantine_required=True,
            failure_reason="Unable to decode the uploaded file with the detected encoding.",
        )

    normalized_text = _normalize_text(decoded_text)
    delimiter_detected = _detect_delimiter(normalized_text)

    return PreParseNormalizationResult(
        normalized_text=normalized_text,
        encoding_detected=encoding_detected,
        delimiter_detected=delimiter_detected,
    )


def _detect_encoding(file_bytes: bytes) -> str | None:
    if file_bytes.startswith(b"\xef\xbb\xbf"):
        return "utf-8-sig"
    if file_bytes.startswith(b"\xff\xfe") or file_bytes.startswith(b"\xfe\xff"):
        return "utf-16"

    for candidate in ("utf-8", "cp1252"):
        try:
            file_bytes.decode(candidate)
            return candidate
        except UnicodeDecodeError:
            continue

    return None


def _normalize_text(text: str) -> str:
    normalized_text = text.replace("\r\n", "\n").replace("\r", "\n")
    return normalized_text.removeprefix("\ufeff")


def _detect_delimiter(text: str) -> str | None:
    sample_lines = [line for line in text.splitlines() if line.strip()][:20]
    if not sample_lines:
        return None

    sample = "\n".join(sample_lines)
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters="".join(SUPPORTED_DELIMITERS))
        return dialect.delimiter
    except csv.Error:
        return _delimiter_by_frequency(sample_lines)


def _delimiter_by_frequency(lines: Iterable[str]) -> str | None:
    counts = {
        delimiter: sum(line.count(delimiter) for line in lines)
        for delimiter in SUPPORTED_DELIMITERS
    }
    best_delimiter = max(counts, key=lambda delimiter: counts[delimiter])
    if counts[best_delimiter] == 0:
        return None

    return best_delimiter
