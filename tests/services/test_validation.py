"""Tests for import validation decisions."""

from datetime import date
from decimal import Decimal
from uuid import uuid4

from app.models.parsing import ParserInspectionResult
from app.models.validation import ValidationCheckStatus
from app.services.validation import build_validation_report
from tests.factories import canonical_transaction


def _inspection_result(**updates: object) -> ParserInspectionResult:
    baseline = {
        "parser_name": "test_parser",
        "parser_version": "v1",
        "header_detected": True,
        "raw_rows_recorded": 2,
        "accepted_rows_recorded": 1,
        "ignored_rows_recorded": 1,
        "suspicious_rows_recorded": 0,
    }
    baseline.update(updates)
    return ParserInspectionResult.model_validate(baseline)


def test_validation_fails_quarantined_file_with_default_reason() -> None:
    report = build_validation_report(
        file_id=uuid4(),
        inspection_result=_inspection_result(raw_rows_recorded=0, header_detected=False),
        supports_canonical_mapping=True,
        quarantine_required=True,
    )

    assert report.final_status == "FAIL_NEEDS_REVIEW"
    assert report.reconciliation_status == ValidationCheckStatus.FAIL
    assert report.ledger_continuity_status == ValidationCheckStatus.SKIPPED
    assert report.messages == ["File could not be normalized and was quarantined before parsing."]


def test_validation_fails_when_header_rows_and_transactions_are_missing() -> None:
    report = build_validation_report(
        file_id=uuid4(),
        inspection_result=_inspection_result(
            header_detected=False,
            raw_rows_recorded=0,
            accepted_rows_recorded=0,
            ignored_rows_recorded=0,
        ),
        supports_canonical_mapping=True,
        quarantine_required=False,
    )

    assert report.final_status == "FAIL_NEEDS_REVIEW"
    assert "No transaction header row was detected." in report.messages
    assert "No readable rows were recorded during parser inspection." in report.messages
    assert "No canonical transactions were imported." in report.messages


def test_validation_warns_for_suspicious_duplicate_and_ambiguous_rows() -> None:
    report = build_validation_report(
        file_id=uuid4(),
        inspection_result=_inspection_result(
            suspicious_rows_recorded=2,
            duplicate_transactions_detected=3,
            exact_duplicate_transactions=2,
            probable_duplicate_transactions=1,
            ambiguous_transactions_detected=1,
            accepted_rows_recorded=0,
            transactions_imported=0,
        ),
        supports_canonical_mapping=True,
        quarantine_required=False,
    )

    assert report.final_status == "PASS_WITH_WARNINGS"
    assert report.reconciliation_status == ValidationCheckStatus.WARN
    assert report.ledger_continuity_status == ValidationCheckStatus.WARN
    assert "2 suspicious rows need review." in report.messages
    assert "3 duplicate transactions were skipped." in report.messages
    assert (
        "No new transactions were imported because all rows duplicated existing ledger rows."
        in (report.messages)
    )


def test_validation_fails_invalid_statement_dates_and_non_positive_amounts() -> None:
    transaction = canonical_transaction(amount=Decimal("0.00"))
    report = build_validation_report(
        file_id=uuid4(),
        inspection_result=_inspection_result(
            statement_start_date=date(2026, 4, 2),
            statement_end_date=date(2026, 4, 1),
            canonical_transactions=[transaction],
        ),
        supports_canonical_mapping=True,
        quarantine_required=False,
    )

    assert report.final_status == "FAIL_NEEDS_REVIEW"
    assert "Statement start date is after statement end date." in report.messages
    assert "One or more canonical transactions have a non-positive amount." in report.messages


def test_validation_warns_when_transactions_fall_outside_statement_period() -> None:
    transaction = canonical_transaction(transaction_date=date(2026, 5, 1))
    report = build_validation_report(
        file_id=uuid4(),
        inspection_result=_inspection_result(
            statement_start_date=date(2026, 4, 1),
            statement_end_date=date(2026, 4, 30),
            canonical_transactions=[transaction],
        ),
        supports_canonical_mapping=True,
        quarantine_required=False,
    )

    assert report.final_status == "PASS_WITH_WARNINGS"
    assert "One or more transactions fall outside the statement date range." in report.messages
    assert "1 canonical transactions were imported." in report.messages


def test_validation_passes_non_canonical_audit_only_import() -> None:
    report = build_validation_report(
        file_id=uuid4(),
        inspection_result=_inspection_result(transactions_imported=0),
        supports_canonical_mapping=False,
        quarantine_required=False,
    )

    assert report.final_status == "PASS"
    assert report.ledger_continuity_status == ValidationCheckStatus.SKIPPED
