"""Validation and reconciliation checks for completed imports."""

from datetime import date
from decimal import Decimal
from uuid import UUID, uuid4

from app.models.imports import ImportStatus
from app.models.ledger import CanonicalTransactionRecord, TransactionDirection
from app.models.parsing import ParserInspectionResult
from app.models.validation import (
    ValidationCheckStatus,
    ValidationIssueRecord,
    ValidationIssueSeverity,
    ValidationReportRecord,
)


def build_validation_report(
    *,
    file_id: UUID,
    inspection_result: ParserInspectionResult,
    supports_canonical_mapping: bool,
    quarantine_required: bool,
    normalization_failure_reason: str | None = None,
) -> ValidationReportRecord:
    """Build a conservative import validation report from parser output."""

    failure_issues: list[ValidationIssueRecord] = []
    warning_issues: list[ValidationIssueRecord] = []
    informational_issues: list[ValidationIssueRecord] = []

    if quarantine_required:
        failure_issues.append(
            _issue(
                severity=ValidationIssueSeverity.ERROR,
                code="file_quarantined",
                title="File could not be read",
                detail=normalization_failure_reason
                or "File could not be normalized and was quarantined before parsing.",
                suggested_action="Check the file encoding and upload a readable CSV export.",
            )
        )

    if not inspection_result.header_detected and not quarantine_required:
        failure_issues.append(
            _issue(
                severity=ValidationIssueSeverity.ERROR,
                code="header_missing",
                title="Transaction header not detected",
                detail="No transaction header row was detected.",
                suggested_action="Check whether this bank export format needs a parser update.",
            )
        )

    if inspection_result.raw_rows_recorded == 0 and not quarantine_required:
        failure_issues.append(
            _issue(
                severity=ValidationIssueSeverity.ERROR,
                code="no_readable_rows",
                title="No readable rows",
                detail="No readable rows were recorded during parser inspection.",
                suggested_action="Confirm the uploaded file is a CSV statement export.",
            )
        )

    if inspection_result.suspicious_rows_recorded > 0:
        warning_issues.append(
            _issue(
                severity=ValidationIssueSeverity.WARNING,
                code="suspicious_rows",
                title="Rows need review",
                detail=f"{inspection_result.suspicious_rows_recorded} suspicious rows need review.",
                suggested_action="Open diagnostics and inspect rows marked Needs review.",
                affected_row_count=inspection_result.suspicious_rows_recorded,
            )
        )

    if inspection_result.duplicate_transactions_detected > 0:
        warning_issues.append(
            _issue(
                severity=ValidationIssueSeverity.WARNING,
                code="duplicate_transactions",
                title="Duplicate transactions skipped",
                detail=(
                    f"{inspection_result.duplicate_transactions_detected} duplicate transactions "
                    "were skipped."
                ),
                suggested_action=(
                    "Review duplicate counts if the statement overlaps another import."
                ),
                affected_row_count=inspection_result.duplicate_transactions_detected,
            )
        )

    if inspection_result.ambiguous_transactions_detected > 0:
        warning_issues.append(
            _issue(
                severity=ValidationIssueSeverity.WARNING,
                code="ambiguous_duplicates",
                title="Ambiguous duplicate confidence",
                detail=(
                    f"{inspection_result.ambiguous_transactions_detected} transactions were "
                    "imported "
                    "with ambiguous duplicate confidence."
                ),
                suggested_action="Check the imported transactions before relying on totals.",
                affected_row_count=inspection_result.ambiguous_transactions_detected,
            )
        )

    if supports_canonical_mapping and inspection_result.transactions_imported == 0:
        if inspection_result.duplicate_transactions_detected > 0:
            warning_issues.append(
                _issue(
                    severity=ValidationIssueSeverity.WARNING,
                    code="all_rows_duplicate",
                    title="No new transactions",
                    detail=(
                        "No new transactions were imported because all rows duplicated "
                        "existing ledger rows."
                    ),
                    suggested_action="No action is needed if this was an intentional re-upload.",
                    affected_row_count=inspection_result.duplicate_transactions_detected,
                )
            )
        elif not quarantine_required:
            failure_issues.append(
                _issue(
                    severity=ValidationIssueSeverity.ERROR,
                    code="no_transactions_imported",
                    title="No transactions imported",
                    detail="No canonical transactions were imported.",
                    suggested_action="Review diagnostics to identify parser or CSV format gaps.",
                )
            )

    if inspection_result.statement_start_date and inspection_result.statement_end_date:
        if inspection_result.statement_start_date > inspection_result.statement_end_date:
            failure_issues.append(
                _issue(
                    severity=ValidationIssueSeverity.ERROR,
                    code="invalid_statement_period",
                    title="Invalid statement period",
                    detail="Statement start date is after statement end date.",
                    suggested_action="Check parser date extraction for this bank export.",
                )
            )

    if _has_non_positive_amount(inspection_result):
        failure_issues.append(
            _issue(
                severity=ValidationIssueSeverity.ERROR,
                code="non_positive_amount",
                title="Invalid transaction amount",
                detail="One or more canonical transactions have a non-positive amount.",
                suggested_action="Review parser amount mapping before trusting this import.",
            )
        )

    if _has_transaction_outside_statement_period(inspection_result):
        warning_issues.append(
            _issue(
                severity=ValidationIssueSeverity.WARNING,
                code="transaction_outside_statement_period",
                title="Transaction outside statement period",
                detail="One or more transactions fall outside the statement date range.",
                suggested_action="Check the statement period and transaction date columns.",
            )
        )

    balance_mismatch_count = _running_balance_mismatch_count(inspection_result)
    if balance_mismatch_count > 0:
        warning_issues.append(
            _issue(
                severity=ValidationIssueSeverity.WARNING,
                code="running_balance_mismatch",
                title="Running balance mismatch",
                detail=(
                    "Running balance continuity mismatches were detected across "
                    f"{balance_mismatch_count} transitions."
                ),
                suggested_action=(
                    "Review balance-bearing transactions for parser or bank-format issues."
                ),
                affected_row_count=balance_mismatch_count,
            )
        )

    if supports_canonical_mapping and inspection_result.transactions_imported > 0:
        informational_issues.append(
            _issue(
                severity=ValidationIssueSeverity.INFO,
                code="transactions_imported",
                title="Transactions imported",
                detail=(
                    f"{inspection_result.transactions_imported} canonical transactions were "
                    "imported."
                ),
                suggested_action="No action is required.",
                affected_row_count=inspection_result.transactions_imported,
            )
        )

    reconciliation_status = _derive_reconciliation_status(
        failure_issues=failure_issues,
        warning_issues=warning_issues,
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
        issues=[*failure_issues, *warning_issues, *informational_issues],
    )


def _derive_reconciliation_status(
    *,
    failure_issues: list[ValidationIssueRecord],
    warning_issues: list[ValidationIssueRecord],
) -> ValidationCheckStatus:
    if failure_issues:
        return ValidationCheckStatus.FAIL

    if warning_issues:
        return ValidationCheckStatus.WARN

    return ValidationCheckStatus.PASS


def _issue(
    *,
    severity: ValidationIssueSeverity,
    code: str,
    title: str,
    detail: str,
    suggested_action: str,
    affected_row_count: int = 0,
) -> ValidationIssueRecord:
    return ValidationIssueRecord(
        severity=severity,
        code=code,
        title=title,
        detail=detail,
        suggested_action=suggested_action,
        affected_row_count=affected_row_count,
    )


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
        _effective_period_date(transaction) < inspection_result.statement_start_date
        or _effective_period_date(transaction) > inspection_result.statement_end_date
        for transaction in inspection_result.canonical_transactions
    )


def _effective_period_date(transaction: CanonicalTransactionRecord) -> date:
    return transaction.value_date or transaction.transaction_date


def _running_balance_mismatch_count(inspection_result: ParserInspectionResult) -> int:
    balance_rows = [
        transaction
        for transaction in sorted(
            inspection_result.canonical_transactions,
            key=lambda transaction: transaction.source_row_number,
        )
        if transaction.balance is not None
    ]
    if len(balance_rows) < 2:
        return 0

    source_order = _infer_source_date_order(balance_rows)
    if source_order == "ascending":
        return _running_balance_mismatch_count_forward(
            balance_rows,
            skip_date_discontinuities=True,
        )

    if source_order == "descending":
        return _running_balance_mismatch_count_reverse(
            balance_rows,
            skip_date_discontinuities=True,
        )

    forward_mismatches = _running_balance_mismatch_count_forward(
        balance_rows,
        skip_date_discontinuities=True,
    )
    reverse_mismatches = _running_balance_mismatch_count_reverse(
        balance_rows,
        skip_date_discontinuities=True,
    )
    return min(forward_mismatches, reverse_mismatches)


def _running_balance_mismatch_count_forward(
    transactions: list[CanonicalTransactionRecord],
    *,
    skip_date_discontinuities: bool = False,
) -> int:
    mismatches = 0
    previous: CanonicalTransactionRecord | None = None
    for current in transactions:
        if previous is None:
            previous = current
            continue

        previous_balance = previous.balance
        if previous_balance is None:
            previous = current
            continue

        if skip_date_discontinuities and current.transaction_date == previous.transaction_date:
            previous = None
            continue

        if skip_date_discontinuities and current.transaction_date < previous.transaction_date:
            previous = current
            continue

        expected_balance = previous_balance + _signed_amount(current)
        if _is_balance_mismatch(current.balance, expected_balance):
            mismatches += 1

        previous = current

    return mismatches


def _running_balance_mismatch_count_reverse(
    transactions: list[CanonicalTransactionRecord],
    *,
    skip_date_discontinuities: bool = False,
) -> int:
    mismatches = 0
    previous: CanonicalTransactionRecord | None = None
    for current in transactions:
        if previous is None:
            previous = current
            continue

        previous_balance = previous.balance
        if previous_balance is None:
            previous = current
            continue

        if skip_date_discontinuities and current.transaction_date == previous.transaction_date:
            previous = None
            continue

        if skip_date_discontinuities and current.transaction_date > previous.transaction_date:
            previous = current
            continue

        expected_balance = previous_balance - _signed_amount(previous)
        if _is_balance_mismatch(current.balance, expected_balance):
            mismatches += 1

        previous = current

    return mismatches


def _infer_source_date_order(
    transactions: list[CanonicalTransactionRecord],
) -> str | None:
    ascending_pairs = 0
    descending_pairs = 0
    for previous, current in zip(transactions, transactions[1:], strict=False):
        if current.transaction_date > previous.transaction_date:
            ascending_pairs += 1
        elif current.transaction_date < previous.transaction_date:
            descending_pairs += 1

    if ascending_pairs > descending_pairs:
        return "ascending"

    if descending_pairs > ascending_pairs:
        return "descending"

    return None


def _signed_amount(transaction: CanonicalTransactionRecord) -> Decimal:
    if transaction.direction == TransactionDirection.CREDIT:
        return transaction.amount

    return -transaction.amount


def _is_balance_mismatch(actual_balance: Decimal | None, expected_balance: Decimal) -> bool:
    if actual_balance is None:
        return False

    return abs(actual_balance - expected_balance) > Decimal("0.01")
