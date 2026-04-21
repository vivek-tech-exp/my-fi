"""Validation and reconciliation checks for completed imports."""

from uuid import UUID, uuid4

from app.models.imports import ImportStatus
from app.models.parsing import ParserInspectionResult
from app.models.validation import ValidationCheckStatus, ValidationReportRecord


def build_validation_report(
    *,
    file_id: UUID,
    inspection_result: ParserInspectionResult,
    supports_canonical_mapping: bool,
    quarantine_required: bool,
    normalization_failure_reason: str | None = None,
) -> ValidationReportRecord:
    """Build a conservative import validation report from parser output."""

    failure_messages: list[str] = []
    warning_messages: list[str] = []
    informational_messages: list[str] = []

    if quarantine_required:
        failure_messages.append(
            normalization_failure_reason
            or "File could not be normalized and was quarantined before parsing."
        )

    if not inspection_result.header_detected and not quarantine_required:
        failure_messages.append("No transaction header row was detected.")

    if inspection_result.raw_rows_recorded == 0 and not quarantine_required:
        failure_messages.append("No readable rows were recorded during parser inspection.")

    if inspection_result.suspicious_rows_recorded > 0:
        warning_messages.append(
            f"{inspection_result.suspicious_rows_recorded} suspicious rows need review."
        )

    if inspection_result.duplicate_transactions_detected > 0:
        warning_messages.append(
            f"{inspection_result.duplicate_transactions_detected} duplicate transactions "
            "were skipped."
        )

    if inspection_result.ambiguous_transactions_detected > 0:
        warning_messages.append(
            f"{inspection_result.ambiguous_transactions_detected} transactions were imported "
            "with ambiguous duplicate confidence."
        )

    if supports_canonical_mapping and inspection_result.transactions_imported == 0:
        if inspection_result.duplicate_transactions_detected > 0:
            warning_messages.append(
                "No new transactions were imported because all rows duplicated "
                "existing ledger rows."
            )
        elif not quarantine_required:
            failure_messages.append("No canonical transactions were imported.")

    if inspection_result.statement_start_date and inspection_result.statement_end_date:
        if inspection_result.statement_start_date > inspection_result.statement_end_date:
            failure_messages.append("Statement start date is after statement end date.")

    if _has_non_positive_amount(inspection_result):
        failure_messages.append("One or more canonical transactions have a non-positive amount.")

    if _has_transaction_outside_statement_period(inspection_result):
        warning_messages.append("One or more transactions fall outside the statement date range.")

    if supports_canonical_mapping and inspection_result.transactions_imported > 0:
        informational_messages.append(
            f"{inspection_result.transactions_imported} canonical transactions were imported."
        )

    reconciliation_status = _derive_reconciliation_status(
        failure_messages=failure_messages,
        warning_messages=warning_messages,
    )
    ledger_continuity_status = _derive_ledger_continuity_status(inspection_result)
    final_status = _derive_final_status(
        reconciliation_status=reconciliation_status,
        ledger_continuity_status=ledger_continuity_status,
    )

    return ValidationReportRecord(
        report_id=uuid4(),
        file_id=file_id,
        total_rows=inspection_result.raw_rows_recorded,
        accepted_rows=inspection_result.accepted_rows_recorded,
        ignored_rows=inspection_result.ignored_rows_recorded,
        suspicious_rows=inspection_result.suspicious_rows_recorded,
        duplicate_rows=inspection_result.duplicate_transactions_detected,
        transactions_imported=inspection_result.transactions_imported,
        reconciliation_status=reconciliation_status,
        ledger_continuity_status=ledger_continuity_status,
        final_status=final_status.value,
        messages=[*failure_messages, *warning_messages, *informational_messages],
    )


def _derive_reconciliation_status(
    *,
    failure_messages: list[str],
    warning_messages: list[str],
) -> ValidationCheckStatus:
    if failure_messages:
        return ValidationCheckStatus.FAIL

    if warning_messages:
        return ValidationCheckStatus.WARN

    return ValidationCheckStatus.PASS


def _derive_ledger_continuity_status(
    inspection_result: ParserInspectionResult,
) -> ValidationCheckStatus:
    if inspection_result.ambiguous_transactions_detected > 0:
        return ValidationCheckStatus.WARN

    if inspection_result.duplicate_transactions_detected > 0:
        return ValidationCheckStatus.WARN

    if inspection_result.transactions_imported == 0:
        return ValidationCheckStatus.SKIPPED

    return ValidationCheckStatus.PASS


def _derive_final_status(
    *,
    reconciliation_status: ValidationCheckStatus,
    ledger_continuity_status: ValidationCheckStatus,
) -> ImportStatus:
    if reconciliation_status == ValidationCheckStatus.FAIL:
        return ImportStatus.FAIL_NEEDS_REVIEW

    if (
        reconciliation_status == ValidationCheckStatus.WARN
        or ledger_continuity_status == ValidationCheckStatus.WARN
    ):
        return ImportStatus.PASS_WITH_WARNINGS

    return ImportStatus.PASS


def _has_non_positive_amount(inspection_result: ParserInspectionResult) -> bool:
    return any(transaction.amount <= 0 for transaction in inspection_result.canonical_transactions)


def _has_transaction_outside_statement_period(
    inspection_result: ParserInspectionResult,
) -> bool:
    if not inspection_result.statement_start_date or not inspection_result.statement_end_date:
        return False

    return any(
        transaction.transaction_date < inspection_result.statement_start_date
        or transaction.transaction_date > inspection_result.statement_end_date
        for transaction in inspection_result.canonical_transactions
    )
