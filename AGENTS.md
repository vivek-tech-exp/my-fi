# AGENTS.md — my-fi

> Local-first personal banking ingestion engine.
> Python 3.12+ · FastAPI · DuckDB · uv · ruff · mypy · pytest

---

## ⚡ Token Budget Rules

**Read this file first. Do NOT scan the entire repo.**

1. **Never read** files in these directories — they contain no useful code context:
   - `.mypy_cache/`, `.pytest_cache/`, `.ruff_cache/`, `.playwright-cli/`
   - `.venv/`, `__pycache__/`
   - `docs/` — internal planning docs, not needed for code tasks
   - `samples/` — synthetic test CSVs, only relevant if asked about sample data
   - `app/web/static/` — browser UI assets (HTML/CSS/JS), only read if the task is UI-related

2. **Runtime data lives outside the repo** at `~/.my-fi/`. There are no `data/` or `storage/` directories to scan.

3. **Start narrow.** Read only the files named in this guide for your task type. Expand only if you hit an import you don't understand.

---

## Commands

```bash
make run          # start dev server (uvicorn --reload)
make test         # pytest (100% coverage required)
make lint         # ruff check + ruff format --check + mypy
make clean-cache  # delete tool caches
```

Or without Make:

```bash
uv run uvicorn app.main:app --reload
uv run pytest
uv run ruff check .
uv run mypy app
```

---

## Architecture — Read Order

The codebase has a strict layered dependency flow. **Read top-down, stop when you have enough context.**

```
app/main.py                          ← entrypoint, wires everything
app/core/config.py                   ← Settings (pydantic-settings, env vars)
app/models/                          ← all Pydantic domain models
  imports.py                         ← BankName enum, ImportRecord, upload models
  ledger.py                          ← CanonicalTransactionRecord
  parsing.py                         ← RawRowRecord, ParserInspectionResult
  validation.py                      ← ValidationReport
app/api/routes/                      ← FastAPI route handlers
  imports.py                         ← POST /imports/csv, GET /imports, etc.
  transactions.py                    ← GET /transactions, /transactions/summary
  system.py                          ← GET /, /health
  ui.py                              ← GET /ui (serves static HTML)
app/services/                        ← business logic (called by routes)
  imports.py                         ← upload orchestration, reprocessing
  normalization.py                   ← encoding detection, BOM strip, delimiter detect
  duplicates.py                      ← duplicate transaction detection
  validation.py                      ← import validation and report generation
app/parsers/                         ← bank-specific CSV parsers
  base.py                            ← BaseCsvParser (abstract, shared logic)
  hdfc.py                            ← HDFC parser
  kotak.py                           ← Kotak parser (has preamble/footer handling)
  federal.py                         ← Federal Bank parser
  registry.py                        ← parser lookup by BankName
app/db/                              ← DuckDB access layer (ONLY place that imports duckdb)
  database.py                        ← connection management, schema init
  source_files.py                    ← source_files table CRUD
  raw_rows.py                        ← raw_rows table CRUD
  canonical_transactions.py          ← canonical_transactions table CRUD
  validation_reports.py              ← validation_reports table CRUD
```

### Test structure mirrors app:

```
tests/conftest.py                    ← shared fixtures (monkeypatch all paths to tmp_path)
tests/factories.py                   ← test data factories
tests/api/                           ← route-level integration tests
tests/db/                            ← db layer tests
tests/models/                        ← model tests
tests/services/                      ← service-level tests
```

---

## Code Conventions

- **Type annotations** on every function — mypy strict mode, no exceptions.
- **Pydantic models** in `app/models/` for all data shapes — never use raw dicts.
- **DuckDB access** only through `app/db/` — never `import duckdb` elsewhere.
- **Settings** via `pydantic-settings` in `app/core/config.py` — no hardcoded paths or secrets.
- **Line length** 100, **double quotes** — ruff enforced.
- **Tests** require 100% coverage — `pytest --cov-fail-under=100`.

---

## Task Routing — What to Read per Task Type

### New bank parser
Read: `app/parsers/base.py` → any existing parser (e.g., `hdfc.py`) → `app/models/parsing.py` → `app/models/ledger.py` → `app/parsers/registry.py` → `app/models/imports.py` (BankName enum)
Touch: `app/parsers/<bank>.py` (new), `app/models/imports.py` (add enum), `app/parsers/registry.py` (register), `tests/services/` (new test)

### New API route
Read: `app/api/router.py` → existing route in `app/api/routes/` → `app/models/`
Touch: `app/api/routes/` (new or modify), `app/services/` (if new logic), `tests/api/` (test)

### Database schema change
Read: `app/db/database.py` → the relevant `app/db/` module
Touch: `app/db/`, `app/models/`, tests

### UI change
Read: `app/web/static/index.html` → `app/web/static/main.js` → `app/web/static/components.js`
Touch: files in `app/web/static/` only. The UI is vanilla HTML/CSS/JS served by FastAPI. No build step.

### Config / settings change
Read: `app/core/config.py` → `.env.example`
Touch: `app/core/config.py`, `.env.example`, tests

---

## Do NOT Touch

| Path | Reason |
|---|---|
| `uv.lock` | Auto-managed — update only via `uv add` / `uv sync` |
| `~/.my-fi/` | User's runtime data — never read, write, log, or print contents |
| `samples/*.csv` | Synthetic demo data — only modify if adding a new parser |

---

## Scoping Rules

- **One task = one module.** State the exact file path you're changing.
- **If a change spans more than 3 files**, stop and present a plan first.
- **Never bulk-read the repo.** Use the architecture map above to navigate directly.
- **Run `make test` after every change** — 100% coverage is enforced, regressions fail CI.
