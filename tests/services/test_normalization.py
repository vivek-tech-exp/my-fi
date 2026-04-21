"""Tests for the pre-parse normalization helpers."""

import app.services.normalization as normalization
from app.services.normalization import normalize_uploaded_csv


def test_normalize_uploaded_csv_strips_bom_and_normalizes_line_endings() -> None:
    file_bytes = b"\xef\xbb\xbfDate,Narration,Amount\r\n2026-04-01,Cafe,120.00\r\n"

    result = normalize_uploaded_csv(file_bytes)

    assert result.quarantine_required is False
    assert result.encoding_detected == "utf-8-sig"
    assert result.delimiter_detected == ","
    assert result.normalized_text == "Date,Narration,Amount\n2026-04-01,Cafe,120.00\n"


def test_normalize_uploaded_csv_decodes_cp1252_and_detects_semicolon_delimiter() -> None:
    file_bytes = "Date;Narration\r\n2026-04-01;Café\r\n".encode("cp1252")

    result = normalize_uploaded_csv(file_bytes)

    assert result.quarantine_required is False
    assert result.encoding_detected == "cp1252"
    assert result.delimiter_detected == ";"
    assert result.normalized_text == "Date;Narration\n2026-04-01;Café\n"


def test_normalize_uploaded_csv_marks_unreadable_bytes_for_quarantine() -> None:
    result = normalize_uploaded_csv(b"\x81\x8d\x8f\x90")

    assert result.quarantine_required is True
    assert result.failure_reason is not None
    assert result.encoding_detected is None
    assert result.delimiter_detected is None


def test_normalize_uploaded_csv_decodes_utf16_and_detects_tab_delimiter() -> None:
    file_bytes = "Date\tNarration\r2026-04-01\tCafe\r".encode("utf-16")

    result = normalize_uploaded_csv(file_bytes)

    assert result.quarantine_required is False
    assert result.encoding_detected == "utf-16"
    assert result.delimiter_detected == "\t"
    assert result.normalized_text == "Date\tNarration\n2026-04-01\tCafe\n"


def test_normalize_uploaded_csv_quarantines_when_detected_encoding_fails(
    monkeypatch,
) -> None:
    monkeypatch.setattr(normalization, "_detect_encoding", lambda _: "utf-8")

    result = normalize_uploaded_csv(b"\xff")

    assert result.quarantine_required is True
    assert result.failure_reason == "Unable to decode the uploaded file with the detected encoding."


def test_normalize_uploaded_csv_handles_empty_and_delimiterless_text() -> None:
    empty_result = normalize_uploaded_csv(b"")
    plain_result = normalize_uploaded_csv(b"header\nrow\n")

    assert empty_result.delimiter_detected is None
    assert plain_result.delimiter_detected is None


def test_delimiter_frequency_fallback_returns_most_common_delimiter() -> None:
    assert normalization._delimiter_by_frequency(["a|b", "c|d"]) == "|"
