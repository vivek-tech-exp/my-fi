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

The current completed milestone on `master` is `P1: Upload API and local file storage`.

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

DuckDB now backs the source file registry. Transaction, report, and reconciliation tables will be added in later milestones.

## Project Layout

```text
app/
  api/
  core/
  db/
  models/
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

At this stage, the endpoint stores the uploaded file locally, computes its SHA-256 hash, persists a `source_files` registry row in DuckDB, and returns structured metadata. Idempotency and parsing arrive in the next milestones.

The registry currently tracks:

* file identity and hash metadata
* current import lifecycle status
* parser version
* placeholder fields for statement and file-detection metadata

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
