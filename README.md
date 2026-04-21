# my-fi

Local-first personal banking ingestion engine for importing multi-bank CSV exports into a trusted canonical ledger.

## Current Docs

* Product requirements: [docs/PRD_version_1.md](docs/PRD_version_1.md)
* Implementation roadmap: [docs/implementation_plan_v1.md](docs/implementation_plan_v1.md)
* Engineering standards: [docs/CODING_STANDARDS.md](docs/CODING_STANDARDS.md)

## Working Model

This repository is being built in small vertical slices.

* planning and baseline standards can land directly on `master`
* feature development should happen on short-lived branches
* changes should merge back to `master` through pull requests

The current completed milestone on `master` is `P7: duplicate transaction protection`.

## Project Overview

V1 is intentionally backend-first.

The service will:

* accept bank CSV uploads through a FastAPI API
* store source files locally
* normalize and parse bank-specific CSV formats
* build a canonical transaction ledger
* validate imports before they are trusted

The current branch-by-branch roadmap starts with the FastAPI foundation and then layers in uploads, persistence, parsing, and validation.

## Tech Stack

* Python
* FastAPI
* DuckDB
* `uv` for dependency management and local execution
* Pydantic and `pydantic-settings`
* `pytest`, `ruff`, and `mypy` for quality checks

DuckDB now backs the source file registry, raw-row audit trail, and canonical Kotak transaction ledger. Report and reconciliation tables will be added in later milestones.

## Project Layout

```text
app/
  api/
  core/
  db/
  models/
  parsers/
  services/
data/
  uploads/
  quarantine/
docs/
storage/
tests/
  fixtures/
```

## Local Setup

### Prerequisites

* Python 3.12 or newer
* `uv`

Install `uv` if needed:

```bash
brew install uv
```

### Install dependencies

```bash
uv sync --dev
```

### Optional environment file

```bash
cp .env.example .env
```

The defaults are already suitable for local development, so `.env` is optional.

## Run the API

Start the local FastAPI server:

```bash
uv run uvicorn app.main:app --reload
```

Then open:

* Swagger UI: `http://127.0.0.1:8000/docs`
* OpenAPI JSON: `http://127.0.0.1:8000/openapi.json`
* Health check: `http://127.0.0.1:8000/health`

## Current API Surface

Available now:

* `GET /`
* `GET /health`
* `POST /imports/csv`

The upload endpoint accepts:

* multipart `file`
* `bank_name`
* optional `account_id`

Current supported bank names:

* `hdfc`
* `kotak`
* `federal`

At this stage, the endpoint stores the uploaded file locally, computes its SHA-256 hash, persists a `source_files` registry row in DuckDB, runs the bank parser, and returns structured metadata.

Re-uploading the same file content is idempotent:

* the existing import metadata is returned
* no second registry row is created
* no second stored file is written

Uploads now also run through pre-parse normalization before later parser work:

* file encoding is detected when possible
* UTF-8 BOM is stripped during normalization
* line endings are normalized to `\n`
* CSV delimiter is detected when possible
* unreadable files are quarantined and marked `FAIL_NEEDS_REVIEW`

Each readable upload now also leaves a raw-row audit trail:

* the parser is selected per bank
* header rows are detected and marked as ignored audit rows
* data rows are classified as `accepted`, `ignored`, or `suspicious`
* every inspected row is persisted in the `raw_rows` DuckDB table
* raw row payloads, parser name, parser version, and rejection reasons are preserved for later debugging

Kotak uploads now also write accepted transaction rows into the canonical ledger:

* account metadata preambles and footer rows are ignored safely
* statement start and end dates are extracted when present
* debit and credit values are normalized into explicit `amount` and `direction`
* accepted rows are written to the `canonical_transactions` DuckDB table
* every canonical transaction keeps source-file and source-row traceability

Canonical transaction inserts now run duplicate protection before ledger writes:

* exact duplicates with balances are skipped
* no-balance fallback duplicates are skipped as probable duplicates
* ambiguous same-account/date/amount candidates are inserted with warning metadata
* upload responses include duplicate and ambiguity counters

The registry currently tracks:

* file identity and hash metadata
* current import lifecycle status
* parser version
* placeholder fields for statement and file-detection metadata
* duplicate-file detection at the file hash level
* detected file encoding and delimiter metadata

The parser audit trail currently tracks:

* parser name and parser version
* row number and raw row text
* parsed row payload
* header-row detection
* suspicious-row reasons for pre-header or malformed rows

## Quality Checks

Run the local quality gates before opening a PR:

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy app
uv run pytest
```

## Git Workflow

Development work should follow the branch and PR standards in [docs/CODING_STANDARDS.md](docs/CODING_STANDARDS.md).

In practice:

* branch from the latest `master`
* implement one scoped change per branch
* merge back through a pull request

Example branch names:

* `feature/bootstrap-fastapi-service`
* `feature/import-upload-api`
* `feature/hdfc-parser`
