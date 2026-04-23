"""Tests for user-facing API response model helpers."""

from uuid import uuid4

from app.models.imports import ImportStatus, ImportSummaryResponse
from app.models.validation import (
    ValidationIssueRecord,
    ValidationIssueSeverity,
    ValidationReportRecord,
)
from tests.factories import source_file_record, validation_report


def test_import_summary_derives_action_fields_for_all_statuses() -> None:
    failed = ImportSummaryResponse.from_source_file_record(
        source_file_record(import_status=ImportStatus.FAIL_NEEDS_REVIEW),
        report=validation_report(file_id=uuid4(), final_status=ImportStatus.FAIL_NEEDS_REVIEW),
    )
    warning = ImportSummaryResponse.from_source_file_record(
        source_file_record(import_status=ImportStatus.PASS_WITH_WARNINGS),
        report=validation_report(file_id=uuid4(), final_status=ImportStatus.PASS_WITH_WARNINGS),
    )
    ready = ImportSummaryResponse.from_source_file_record(
        source_file_record(import_status=ImportStatus.PASS),
        report=validation_report(file_id=uuid4(), final_status=ImportStatus.PASS),
    )
    processing = ImportSummaryResponse.from_source_file_record(
        source_file_record(import_status=ImportStatus.PROCESSING)
    )
    received_without_report = ImportSummaryResponse.from_source_file_record(
        source_file_record(import_status=ImportStatus.RECEIVED)
    )
    received_with_report = ImportSummaryResponse.from_source_file_record(
        source_file_record(import_status=ImportStatus.RECEIVED),
        report=validation_report(file_id=uuid4(), final_status=ImportStatus.RECEIVED),
    )

    assert failed.trust_status == "needs_review"
    assert failed.recommended_action.startswith("Review validation issues")
    assert warning.trust_status == "review_warnings"
    assert warning.recommended_action.startswith("Review warnings")
    assert ready.trust_status == "ready"
    assert ready.recommended_action == "Ready for ledger review."
    assert processing.trust_status == "processing"
    assert processing.recommended_action == "Wait for processing to complete."
    assert received_without_report.recommended_action == "Processing details are not available yet."
    assert received_with_report.trust_status == "received"
    assert received_with_report.recommended_action == "Review import details."


def test_validation_report_derives_generic_issues_from_legacy_messages() -> None:
    report = ValidationReportRecord(
        report_id=uuid4(),
        file_id=uuid4(),
        total_rows=0,
        accepted_rows=0,
        ignored_rows=0,
        suspicious_rows=0,
        duplicate_rows=0,
        transactions_imported=0,
        reconciliation_status="FAIL",
        ledger_continuity_status="SKIPPED",
        final_status="FAIL_NEEDS_REVIEW",
        messages=[
            "No transaction header row was detected.",
            "2 suspicious rows need review.",
            "1 canonical transactions were imported.",
        ],
    )

    assert [issue.severity for issue in report.issues] == [
        ValidationIssueSeverity.ERROR,
        ValidationIssueSeverity.WARNING,
        ValidationIssueSeverity.INFO,
    ]


def test_validation_report_derives_messages_from_structured_issues() -> None:
    report = ValidationReportRecord(
        report_id=uuid4(),
        file_id=uuid4(),
        total_rows=1,
        accepted_rows=1,
        ignored_rows=0,
        suspicious_rows=0,
        duplicate_rows=0,
        transactions_imported=1,
        reconciliation_status="PASS",
        ledger_continuity_status="PASS",
        final_status="PASS",
        issues=[
            ValidationIssueRecord(
                severity=ValidationIssueSeverity.INFO,
                code="transactions_imported",
                title="Transactions imported",
                detail="1 canonical transactions were imported.",
                suggested_action="No action is required.",
            )
        ],
    )

    assert report.messages == ["1 canonical transactions were imported."]
