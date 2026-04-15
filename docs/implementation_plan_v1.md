# V1 Banking Ingestion Implementation Plan

## Summary

This plan turns the V1 PRD into an execution sequence for a local-first FastAPI service that ingests bank CSV files into a canonical DuckDB ledger.

The delivery strategy is:

1. build the runnable service foundation first
2. make the upload API usable from FastAPI Swagger UI at `/docs`
3. ship one full bank vertical slice end to end with HDFC
4. add validation, reporting, and safe reprocessing
5. extend parser coverage to Kotak and Federal without collapsing bank-specific logic

Project defaults for V1:

* Python project tooling: `uv`
* API docs and upload UI: FastAPI built-in Swagger UI
* parser rollout: one bank at a time
* first bank: HDFC

---

## Prioritized Execution Order

### P0. Bootstrap the runnable service

Priority: highest

Goal: create the minimal project skeleton so the app can run locally and Swagger UI is available immediately.

Scope:

* create Python project structure with `pyproject.toml`
* add FastAPI app entrypoint
* add environment and settings layer
* create runtime folders:
  * `data/uploads`
  * `data/quarantine`
  * `storage`
  * `tests/fixtures`
* update `.gitignore` for runtime files
* update `README.md` with:
  * project overview
  * local setup with `uv`
  * how to run the API
  * how to open `/docs`

Done when:

* `uv run uvicorn app.main:app --reload` starts successfully
* `/docs` loads in the browser
* the repo has a clean initial backend structure

---

### P1. Upload API and local file storage

Priority: highest

Goal: make file upload usable before any parser logic is added.

Scope:

* implement `POST /imports/csv`
* accept multipart file upload
* accept `bank_name`
* accept optional `account_id`
* compute file SHA-256 hash before processing
* store the original uploaded file locally under deterministic bank-scoped paths
* keep original filename for traceability
* return a structured response with import metadata

Decisions:

* use Swagger UI as the first manual test surface
* keep upload storage layout deterministic and bank-specific
* preserve original file bytes on disk before any normalization

Done when:

* a CSV can be uploaded from `/docs`
* the file is saved under a stable local path
* the response includes `file_id`, `file_hash`, `bank_name`, and status

---

### P2. Source file registry and import lifecycle

Priority: highest

Goal: add traceability and safe import state tracking.

Scope:

* initialize DuckDB storage
* create `source_files` table
* persist:
  * `file_id`
  * `original_filename`
  * `stored_path`
  * `bank_name`
  * `account_id`
  * `file_hash`
  * `uploaded_at`
  * `parser_version`
  * `import_status`
  * `statement_start_date`
  * `statement_end_date`
  * `encoding_detected`
  * `delimiter_detected`
* introduce import lifecycle states:
  * `RECEIVED`
  * `PROCESSING`
  * `PASS`
  * `PASS_WITH_WARNINGS`
  * `FAIL_NEEDS_REVIEW`

Done when:

* every uploaded file gets a persistent registry record
* the API can return consistent state for an import
* import state transitions are explicit and auditable

---

### P3. File-level idempotency

Priority: highest

Goal: ensure the same file content is never imported twice.

Scope:

* enforce uniqueness on `file_hash`
* if the same file is uploaded again:
  * return the existing successful import result
  * or return the current processing state
* avoid duplicate writes into downstream tables for the same file content

Done when:

* re-uploading identical bytes does not create a second import
* same file content always maps to the same import record

---

### P4. Pre-parse normalization pipeline

Priority: high

Goal: normalize raw CSV files into a safer intermediate form before parser-specific logic runs.

Scope:

* detect encoding
* normalize to UTF-8
* strip BOM if present
* standardize line endings
* detect delimiter
* preserve original bytes for traceability
* quarantine unreadable or suspicious files
* persist normalization metadata in `source_files`

Done when:

* non-UTF8 inputs can be normalized or quarantined safely
* delimiter and encoding are recorded
* the parser receives predictable normalized input

---

### P5. Parser framework and raw row audit trail

Priority: high

Goal: create a bank-specific parser architecture that preserves row-level auditability.

Scope:

* define parser contract per bank
* support:
  * header row detection
  * fluff row detection
  * malformed row repair hooks
  * parser versioning
  * canonical mapping hooks
* create `raw_rows` table
* persist for every inspected row:
  * `file_id`
  * `row_number`
  * `raw_row_json`
  * `row_type`
  * `parse_status`
  * `rejection_reason`
  * `parser_name`
  * `parser_version`
* classify rows as:
  * `accepted`
  * `ignored`
  * `suspicious`

Done when:

* all parser logic is bank-isolated
* every source row is traceable
* suspicious and ignored rows are preserved for debugging

---

### P6. HDFC end-to-end vertical slice

Priority: high

Goal: prove the full ingestion pipeline with one real bank implementation.

Scope:

* add anonymized HDFC fixtures covering:
  * clean files
  * noisy files
  * repeated headers
  * fluff rows
  * malformed rows
  * narration with commas
  * debit/credit variations
  * balance-present and balance-missing cases
* implement HDFC parser behavior:
  * header detection
  * row repair where needed
  * transaction row detection
  * debit/credit interpretation
  * canonical transaction mapping
* create `canonical_transactions` table
* persist accepted transactions with source-row traceability

Done when:

* an HDFC CSV can be uploaded via `/docs`
* valid transaction rows are imported into the canonical ledger
* ignored and suspicious rows are stored separately

---

### P7. Duplicate transaction protection

Priority: high

Goal: prevent overlapping statement imports from creating duplicate transactions.

Scope:

* implement account-scoped transaction fingerprinting
* exact fingerprint candidate should prefer:
  * `account_id`
  * `transaction_date`
  * `direction`
  * `amount`
  * `balance`
* fallback fingerprint when balance is missing should use:
  * `account_id`
  * `transaction_date`
  * `value_date`
  * `direction`
  * `amount`
  * normalized narration hash
* assign duplicate confidence:
  * `EXACT_DUPLICATE`
  * `PROBABLE_DUPLICATE`
  * `AMBIGUOUS`
  * `UNIQUE`

Done when:

* overlapping files do not silently create duplicate ledger rows
* ambiguity is surfaced rather than hidden

---

### P8. Validation and reconciliation engine

Priority: high

Goal: determine whether an import is trustworthy beyond simple parsing success.

Scope:

* implement statement-level checks:
  * total row count sanity
  * accepted row count sanity
  * amount field sanity
  * debit/credit consistency
  * date range sanity
  * duplicate detection summary
  * balance reconciliation where balance exists
  * running balance continuity where possible
  * suspicious row threshold
* implement ledger-level checks:
  * detect earliest and latest dates in new import
  * compare against prior imported transactions for the same account
  * detect date gaps
  * detect unmatched balance transitions
* set final status:
  * `PASS`
  * `PASS_WITH_WARNINGS`
  * `FAIL_NEEDS_REVIEW`

Done when:

* every import ends with an explicit trust status
* continuity issues are flagged even when a file parses correctly

---

### P9. Import reports and inspection APIs

Priority: medium-high

Goal: make the import process inspectable through APIs without manual database queries.

Scope:

* create `validation_reports` table
* store:
  * total rows
  * accepted rows
  * ignored rows
  * suspicious rows
  * duplicate rows
  * reconciliation status
  * ledger continuity status
  * final status
  * generated timestamp
* implement:
  * `GET /imports`
  * `GET /imports/{file_id}`
  * `GET /imports/{file_id}/report`
  * `GET /imports/{file_id}/rows`

Done when:

* import metadata, row classifications, and validation output are accessible from the API
* `/docs` is enough for manual upload, inspection, and debugging

---

### P10. Reprocessing support

Priority: medium

Goal: allow previously stored files to be re-run with newer parser versions safely.

Scope:

* implement `POST /imports/{file_id}/reprocess`
* re-read stored source file instead of requiring re-upload
* record parser version used for each run
* preserve auditable import history
* ensure reprocessing does not silently overwrite the prior result without traceability

Done when:

* a stored file can be re-run with updated parser logic
* parser version changes remain visible in import history

---

### P11. Extend to Kotak and Federal

Priority: medium

Goal: add full bank coverage using the same ingestion framework while preserving separate parser logic per bank.

Scope:

* add Kotak parser plus fixtures and tests
* add Federal parser plus fixtures and tests
* reuse the same normalization, duplicate detection, validation, and reporting layers
* keep parser modules separated by bank

Done when:

* all three target banks are supported
* bank-specific parsing remains explicit and maintainable

---

## Suggested Internal Architecture

Suggested top-level structure:

```text
app/
  api/
  core/
  db/
  models/
  parsers/
    hdfc/
    kotak/
    federal/
  services/
  storage/
  validation/
data/
  uploads/
  quarantine/
storage/
tests/
  fixtures/
```

Implementation bias:

* keep FastAPI thin
* keep orchestration in service layer
* keep DuckDB access explicit rather than hiding it behind heavy abstractions
* keep parser code isolated by bank
* keep validation independent from parser implementations where possible

---

## Public API Surface for V1

### Upload and processing

* `POST /imports/csv`

### Inspection

* `GET /imports`
* `GET /imports/{file_id}`
* `GET /imports/{file_id}/report`
* `GET /imports/{file_id}/rows`

### Reprocessing

* `POST /imports/{file_id}/reprocess`

---

## Test Strategy

### API smoke tests

* app starts successfully
* `/docs` is reachable
* multipart upload works through FastAPI

### Storage and idempotency tests

* uploaded files are stored under deterministic paths
* same file bytes do not create duplicate imports
* processing state is returned consistently for repeat uploads

### Normalization tests

* UTF-8 files pass through unchanged
* BOM files normalize correctly
* Windows line endings normalize correctly
* delimiter detection works for expected bank files
* unreadable files move to quarantine

### Parser tests

* header detection works
* fluff rows are ignored
* suspicious rows are preserved
* narration fields with commas are handled correctly
* malformed row repair behaves conservatively
* debit/credit mapping is bank-specific and explicit

### Ledger and validation tests

* canonical transactions are traceable to raw rows
* exact duplicates are prevented
* probable duplicates are flagged
* continuity gaps produce warnings
* internally inconsistent files fail review

---

## First Step to Execute

Start with `P0. Bootstrap the runnable service`.

This first implementation step should include:

* create the `uv`-managed Python project
* add FastAPI app skeleton
* make `/docs` available
* add runtime folders
* update `README.md` with setup and run instructions

That gives us a stable base before the upload API work begins.

---

## Working Rules During Execution

* do not build a custom UI before the upload API works in Swagger UI
* do not merge bank-specific parser logic into one generic parser
* do not trust raw CSV rows as transactions until they are classified
* do not trust file parsing success as proof of ledger correctness
* fail safely by warning or quarantining suspicious data instead of silently accepting it

