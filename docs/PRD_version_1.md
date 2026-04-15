# Personal Banking Ingestion Engine — V1 PRD

## 1. Overview

This project is a local-first, backend-only personal banking data ingestion system.

Version 1 focuses on one problem:

**reliably importing multi-bank CSV exports into a trusted canonical transaction ledger without manual row-by-row verification.**

This is **not yet** a personal finance intelligence product. V1 does not attempt categorization, merchant intelligence, insights, notifications, or natural-language querying. Its only job is to create a clean, reusable, trustworthy banking transaction foundation.

---

## 2. Problem Statement

Personal banking data is spread across multiple bank accounts and exported in different CSV formats. Even when CSV is available, the files are not guaranteed to be clean transaction data. They may contain:

* extra header rows
* summary rows
* blank lines
* generated metadata
* opening or closing balance notes
* inconsistent column names
* malformed quoting
* broken delimiters
* narration fields containing commas
* inconsistent row structures across banks and across years

When importing multiple years of data, manual verification becomes impractical. A naive importer is risky because it can silently:

* include non-transaction rows
* miss valid rows
* duplicate transactions
* accept malformed data
* misread debit/credit direction
* produce a ledger that is internally inconsistent
* produce a ledger that looks valid file-by-file but has continuity gaps across time

The real problem is not just file parsing. The real problem is building a **trustworthy ingestion, normalization, and validation pipeline**.

---

## 3. Goal

Create a single source of truth for personal banking transactions by importing CSV exports from multiple banks into one canonical ledger.

V1 should allow the user to:

* upload CSV files through an API
* store uploaded files locally
* parse bank-specific CSV formats
* detect valid transaction rows
* ignore fluff and non-transaction rows
* normalize transactions into a shared schema
* make imports idempotent
* prevent duplicate transactions
* validate statement integrity
* detect ledger continuity gaps across imports
* generate import validation reports
* build a trusted ledger covering at least two years of history

---

## 4. Non-Goals

V1 will **not** include:

* PDF parsing
* credit card statements
* Zerodha or broker data
* mutual funds
* categorization
* merchant normalization
* analytics or insights
* notifications
* natural-language querying
* polished frontend UI
* real-time bank integrations
* multi-user support

---

## 5. Users

Single user only.

This system is intended for personal use. There is no requirement for a consumer-grade UI. Operational clarity, correctness, auditability, and maintainability matter more than presentation.

---

## 6. Product Scope

### In Scope

* CSV ingestion from:

  * HDFC Bank
  * Kotak Bank
  * Federal Bank
* FastAPI-based upload API
* Local storage of source files
* Bank-specific parsing logic
* Encoding normalization and CSV cleanup
* Canonical transaction normalization
* File-level idempotency
* Transaction-level duplicate protection
* Raw row traceability
* Import validation and reconciliation
* Ledger continuity checks across imports
* Import history and reporting APIs

### Out of Scope

* Financial intelligence
* Expense categorization
* Cashflow summaries
* ML or AI
* PDF support
* UI dashboards
* Third-party storage
* Cloud deployment complexity

---

## 7. Core Product Principles

### 7.1 Raw exports are semi-structured

Bank CSV files must be treated as semi-structured input, not trusted transaction data.

### 7.2 Final ledger must be structured

All accepted transaction rows must be transformed into one canonical schema.

### 7.3 Imports must be idempotent

Uploading the same file again must not create duplicate records or corrupt the ledger.

### 7.4 Trust comes from validation

The system must not assume an import is correct just because parsing succeeded. Each import must produce a validation report.

### 7.5 Fail safely

Suspicious files or rows should be isolated, flagged, or rejected rather than silently accepted.

### 7.6 Statement integrity and ledger continuity are separate

A file can be internally valid while the account ledger is still broken because of missing periods. Both must be checked.

### 7.7 Bank-specific normalization beats generic assumptions

Encoding, delimiters, debit/credit interpretation, and row structure must be normalized explicitly per bank.

---

## 8. Functional Requirements

## 8.1 File Upload API

The system must expose an API endpoint to upload CSV files.

### Requirements

* Accept multipart file uploads
* Accept `bank_name` as input
* Optionally accept `account_id`
* Store uploaded file locally
* Compute file hash before processing
* Use file hash for idempotency checks
* Return a structured import response

### Expected behavior

* If file is new: process import
* If file was already successfully imported: return existing result
* If file is currently being processed: return current state
* If file fails validation: mark as failed or warning state
* If file is internally valid but reveals a gap in the ledger: mark as `PASS_WITH_WARNINGS`

---

## 8.2 Local File Storage

Uploaded source files must be stored locally in the repository’s runtime storage area.

### Requirements

* Keep files on disk
* Maintain stable directory structure
* Keep original file name for traceability
* Store files under deterministic paths
* Support quarantine area for failed or suspicious files
* Exclude runtime files from git

### Example structure

```text
project-root/
  app/
  data/
    uploads/
      hdfc/
      kotak/
      federal/
    quarantine/
  storage/
  tests/
```

---

## 8.3 Source File Registry

The system must track every uploaded file in a file registry.

### Required metadata

* `file_id`
* `original_filename`
* `stored_path`
* `bank_name`
* `account_id` if available
* `file_hash`
* `uploaded_at`
* `parser_version`
* `import_status`
* `statement_start_date` if detectable
* `statement_end_date` if detectable
* `encoding_detected`
* `delimiter_detected`

This registry is required for traceability and idempotency.

---

## 8.4 Pre-Parse File Normalization

The system must normalize raw CSV input before bank-specific parsing.

### Required steps

* detect file encoding
* normalize to UTF-8
* strip BOM if present
* standardize line endings
* detect delimiter
* reject or quarantine unreadable files
* preserve original bytes for traceability

### Why this exists

Bank CSVs may contain Windows encodings, BOMs, malformed quoting, and commas inside narration fields. Generic parsing alone is not enough.

---

## 8.5 Bank-Specific CSV Parsing

The system must use separate parsing logic for each bank.

### Why

Even with CSV, each bank may differ in:

* headers
* date formats
* debit/credit fields
* balance fields
* fluff rows
* row layout
* malformed quoting behavior
* narration formatting

### Requirements

* detect actual header row
* ignore irrelevant rows
* map raw values into intermediate parsed rows
* preserve rejected and suspicious rows for auditability
* allow parser versioning for future fixes
* support bank-specific row repair when malformed CSV rows break expected column counts

---

## 8.6 Transaction Row Detection

The system must determine which rows are real transactions.

### Typical rules

A valid transaction row usually contains:

* a valid date
* a non-empty narration or description
* a valid amount signal
* a row shape consistent with the bank format

### Non-transaction examples

* account summary rows
* opening balance lines
* closing balance lines
* blank rows
* exported-on text
* informational notes
* repeated headers within the file

### Row classification

Each raw row must be classified as one of:

* `accepted`
* `ignored`
* `suspicious`

---

## 8.7 Raw Row Preservation

The system must preserve row-level raw data before canonical transformation.

### Required fields

* `file_id`
* `row_number`
* `raw_row_json`
* `row_type`
* `parse_status`
* `rejection_reason` if any
* `parser_name`
* `parser_version`

This ensures every canonical transaction can be traced back to source data.

---

## 8.8 Canonical Transaction Ledger

All accepted rows must be transformed into a common transaction schema.

### Minimum canonical fields

* `transaction_id`
* `source_file_id`
* `bank_name`
* `account_id`
* `transaction_date`
* `value_date` if available
* `description_raw`
* `amount`
* `direction`
* `balance` if available
* `currency`
* `source_row_number`
* `transaction_fingerprint`
* `duplicate_confidence`
* `created_at`

### Canonical rules

* `amount` must be stored as an absolute numeric value
* `direction` must be stored separately as `DEBIT` or `CREDIT`
* raw sign must never be trusted as the sole indicator of debit/credit direction
* amount normalization must be bank-specific and explicit

---

## 8.9 Idempotency

The system must guarantee safe reimport behavior.

### File-level idempotency

The same file content should never be imported twice.

### Strategy

* compute SHA-256 hash of file content
* enforce uniqueness on file hash
* if hash already exists and import succeeded, return prior result

This ensures:

**same file content = same import result**

---

## 8.10 Duplicate Transaction Protection

Even if files differ, overlapping statements may contain the same transactions.

The system must therefore protect against duplicates at the transaction level as well.

### Rules

Duplicate protection must not depend primarily on narration text. Narration, transaction date, and value date may vary slightly across exports.

### Strategy

Use a tiered fingerprinting model.

#### Exact fingerprint candidate

* `account_id`
* `transaction_date`
* `direction`
* `amount`
* `running_balance`
* normalized row type

#### Fallback fingerprint candidate when balance is missing

* `account_id`
* `transaction_date`
* `value_date` if present
* `direction`
* `amount`
* normalized narration hash

### Duplicate confidence levels

* `EXACT_DUPLICATE`
* `PROBABLE_DUPLICATE`
* `AMBIGUOUS`
* `UNIQUE`

The system should use `account_id` as part of duplicate protection and should not assume that `[date + amount + balance]` is universally unique across all cases.

---

## 8.11 Validation and Reconciliation

Every import must run validation checks before being trusted.

### Statement-level validation checks

* total row count sanity
* accepted row count sanity
* amount field sanity
* debit/credit consistency
* date range sanity
* duplicate detection
* balance reconciliation where balance exists
* running balance continuity where possible
* suspicious row threshold

### Ledger-level validation checks

* detect earliest and latest transaction date in the new file
* find the nearest prior imported transaction for the same account
* compare prior closing balance against the inferred opening balance of the new import
* flag discontinuity if there is a date gap or unmatched balance transition

### Final statuses

Each import should end in one of:

* `PASS`
* `PASS_WITH_WARNINGS`
* `FAIL_NEEDS_REVIEW`

### Status interpretation

* `PASS`: file is internally valid and ledger continuity is intact
* `PASS_WITH_WARNINGS`: file is internally valid but there are suspicious rows, continuity gaps, or unresolved duplicate ambiguity
* `FAIL_NEEDS_REVIEW`: file is internally inconsistent or cannot be parsed with enough confidence

---

## 8.12 Import Report

Every import must produce a report summarizing what happened.

### Example report contents

* total CSV rows
* accepted transaction rows
* ignored fluff rows
* suspicious rows
* parser used
* encoding detected
* delimiter detected
* validation checks passed
* validation checks failed
* ledger continuity status
* duplicate summary
* final status
* confidence score if applicable

This report replaces manual row-by-row auditing with statement-level trust.

---

## 9. Hidden Traps and Defensive Rules

### 9.1 Encoding and delimiter issues

Bank CSVs may contain BOMs, Windows encodings, malformed quoting, or commas inside narration fields. The ingestion pipeline must normalize encoding to UTF-8, strip BOMs, standardize line endings, and apply bank-specific row repair logic before canonical parsing.

### 9.2 Duplicate detection is not narration matching

Transaction descriptions, transaction dates, and value dates may vary slightly across exports. Duplicate protection must rely on account-scoped composite fingerprints using stable fields, with running balance as a major signal when available.

### 9.3 Ledger continuity must be validated across imports

A file can be internally correct while still leaving a hole in the overall account ledger. Continuity must be checked against previously imported data for the same account.

### 9.4 Debit/credit polarity drift

Some bank exports use separate debit and credit columns, others use one amount column plus a side indicator, and others use sign conventions that are unsafe to trust blindly. Canonical storage must always separate `amount` from `direction`.

---

## 10. API Requirements

### `POST /imports/csv`

Upload a bank CSV and process it.

#### Input

* multipart file
* `bank_name`
* optional `account_id`

#### Output

* `file_id`
* `file_hash`
* `bank_name`
* duplicate flag
* import status
* row summary
* validation summary

---

### `GET /imports`

List all uploaded imports.

---

### `GET /imports/{file_id}`

Return file-level metadata and import status.

---

### `GET /imports/{file_id}/report`

Return validation report for a file.

---

### `GET /imports/{file_id}/rows`

Return raw row classifications for debugging.

---

### `POST /imports/{file_id}/reprocess`

Re-run parsing for an existing file with a newer parser version.

---

## 11. Data Model

## 11.1 Source Files

Tracks uploaded files.

### Example fields

* `file_id`
* `original_filename`
* `stored_path`
* `bank_name`
* `account_id`
* `file_hash`
* `parser_version`
* `encoding_detected`
* `delimiter_detected`
* `uploaded_at`
* `import_status`

---

## 11.2 Raw Rows

Tracks every parsed row from the source file.

### Example fields

* `raw_row_id`
* `file_id`
* `row_number`
* `raw_row_json`
* `row_type`
* `parse_status`
* `rejection_reason`
* `parser_version`

---

## 11.3 Canonical Transactions

Stores trusted normalized transactions.

### Example fields

* `transaction_id`
* `source_file_id`
* `bank_name`
* `account_id`
* `transaction_date`
* `value_date`
* `description_raw`
* `amount`
* `direction`
* `balance`
* `currency`
* `source_row_number`
* `transaction_fingerprint`
* `duplicate_confidence`
* `created_at`

---

## 11.4 Validation Reports

Stores file-level import results.

### Example fields

* `report_id`
* `file_id`
* `total_rows`
* `accepted_rows`
* `ignored_rows`
* `suspicious_rows`
* `duplicate_rows`
* `reconciliation_status`
* `ledger_continuity_status`
* `final_status`
* `generated_at`

---

## 12. Technical Stack

### Language

Python

### Framework

FastAPI

### Storage

* DuckDB for metadata, transactions, and reports
* local filesystem for source files

### Utilities

* pandas or Polars for CSV parsing and transformation
* Pydantic for request and response models

---

## 13. Why This Stack

This project is primarily:

* ingestion
* normalization
* validation
* reconciliation
* structured local storage

It is not a distributed systems problem. Python is the fastest path for building and iterating on parsing and data quality logic. FastAPI provides a clean API surface and built-in Swagger/OpenAPI support. DuckDB is a strong fit for local-first structured transaction storage.

---

## 14. Success Criteria

V1 is successful if the system can:

* import CSV files from HDFC, Kotak, and Federal
* safely store uploaded files locally
* normalize encoding and delimiters before parsing
* parse only valid transaction rows
* ignore fluff rows reliably
* repair malformed rows where feasible
* normalize accepted data into one canonical ledger
* prevent duplicate imports
* prevent duplicate transactions from overlapping files
* detect ledger continuity gaps
* generate validation reports for every import
* support at least two years of banking history with minimal manual review

---

## 15. Risks

### Format drift

Bank CSV structure may change over time.

### Inconsistent exports

The same bank may produce slightly different files across accounts or years.

### Missing balance data

Some files may not contain enough fields for full reconciliation or strong duplicate matching.

### Ambiguous rows

A few rows may be difficult to classify confidently.

### Overlapping statements

Different exports may contain duplicate transaction windows.

### Incomplete ledger history

The system may receive files with valid internal math but missing intermediate periods.

These risks should be handled through bank-specific parsing, parser versioning, raw row preservation, conservative validation, and ledger continuity checks.

---

## 16. Future Extensions

These are intentionally out of scope for V1, but the architecture should support them later:

* transaction categorization
* merchant normalization
* expense analytics
* daily or monthly summaries
* notifications
* natural-language querying
* investment account ingestion
* credit card support
* PDF parsing

---

## 17. Final V1 Definition

**Version 1 is a FastAPI-based local-first personal banking ingestion service that accepts CSV uploads for HDFC Bank, Kotak Bank, and Federal Bank, stores source files locally, normalizes file encoding and malformed CSV structure, filters non-transaction rows, normalizes valid transactions into a canonical DuckDB ledger, and produces idempotent, validated imports with clear reporting and continuity checks so multi-year banking history can be trusted without manual row-by-row review.**

