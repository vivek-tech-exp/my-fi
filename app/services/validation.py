"""Validation and reconciliation checks for completed imports."""

from datetime import date
from decimal import Decimal
from uuid import UUID, uuid4

from app.models.imports import ImportStatus
from app.models.ledger import CanonicalTransactionRecord, TransactionDirection
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

    balance_mismatch_count = _running_balance_mismatch_count(inspection_result)
    if balance_mismatch_count > 0:
        warning_messages.append(
            "Running balance continuity mismatches were detected across "
            f"{balance_mismatch_count} transitions."
        )

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
