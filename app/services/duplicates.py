"""Duplicate protection for canonical transaction inserts."""

from __future__ import annotations

from dataclasses import dataclass, field
from re import sub

import duckdb

from app.db.canonical_transactions import (
    get_canonical_transaction_by_fingerprint,
    get_potential_duplicate_candidates,
)
from app.models.ledger import CanonicalTransactionRecord, DuplicateConfidence


@dataclass
class DuplicateProtectionResult:
    """Canonical transaction batch after duplicate classification."""

    transactions_to_insert: list[CanonicalTransactionRecord] = field(default_factory=list)
    exact_duplicate_transactions: int = 0
    probable_duplicate_transactions: int = 0
    ambiguous_transactions_detected: int = 0

    @property
    def duplicate_transactions_detected(self) -> int:
        """Return transactions skipped as exact or probable duplicates."""

        return self.exact_duplicate_transactions + self.probable_duplicate_transactions


def apply_duplicate_protection(
    transactions: list[CanonicalTransactionRecord],
    *,
    connection: duckdb.DuckDBPyConnection,
) -> DuplicateProtectionResult:
    """Classify duplicates against existing and in-flight canonical transactions."""

    result = DuplicateProtectionResult()
    staged_transactions: list[CanonicalTransactionRecord] = []
    staged_fingerprints: set[str] = set()

    for transaction in transactions:
        if _is_known_duplicate(transaction, staged_fingerprints, connection):
            _count_skipped_duplicate(transaction, result)
            continue

        transaction_to_insert = transaction
        if _has_ambiguous_candidate(transaction, staged_transactions, connection):
            transaction_to_insert = transaction.model_copy(
                update={"duplicate_confidence": DuplicateConfidence.AMBIGUOUS}
            )
            result.ambiguous_transactions_detected += 1

        result.transactions_to_insert.append(transaction_to_insert)
        staged_transactions.append(transaction_to_insert)
        staged_fingerprints.add(transaction_to_insert.transaction_fingerprint)

    return result


def _is_known_duplicate(
    transaction: CanonicalTransactionRecord,
    staged_fingerprints: set[str],
    connection: duckdb.DuckDBPyConnection,
) -> bool:
    if transaction.transaction_fingerprint in staged_fingerprints:
        return True

    return (
        get_canonical_transaction_by_fingerprint(
            transaction.transaction_fingerprint,
            connection=connection,
        )
        is not None
    )


def _count_skipped_duplicate(
    transaction: CanonicalTransactionRecord,
    result: DuplicateProtectionResult,
) -> None:
    if transaction.balance is None:
        result.probable_duplicate_transactions += 1
        return

    result.exact_duplicate_transactions += 1


def _has_ambiguous_candidate(
    transaction: CanonicalTransactionRecord,
    staged_transactions: list[CanonicalTransactionRecord],
    connection: duckdb.DuckDBPyConnection,
) -> bool:
    candidates = [
        *get_potential_duplicate_candidates(transaction, connection=connection),
        *staged_transactions,
    ]
    return any(_is_ambiguous_match(transaction, candidate) for candidate in candidates)


def _is_ambiguous_match(
    transaction: CanonicalTransactionRecord,
    candidate: CanonicalTransactionRecord,
) -> bool:
    if transaction.transaction_fingerprint == candidate.transaction_fingerprint:
        return False

    if transaction.bank_name != candidate.bank_name:
        return False

    if (transaction.account_id or "") != (candidate.account_id or ""):
        return False

    if transaction.transaction_date != candidate.transaction_date:
        return False

    if transaction.direction != candidate.direction:
        return False

    if transaction.amount != candidate.amount:
        return False

    if (
        transaction.balance is not None
        and candidate.balance is not None
        and transaction.balance != candidate.balance
    ):
        return False

    if transaction.reference_number and transaction.reference_number == candidate.reference_number:
        return True

    return _normalized_description(transaction.description_raw) == _normalized_description(
        candidate.description_raw
    )


def _normalized_description(value: str) -> str:
    return sub(r"\s+", " ", sub(r"[^a-z0-9]+", " ", value.casefold())).strip()
