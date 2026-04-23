# AGENTS.md — my-fi

> Local-first personal banking ingestion engine.
> Python 3.12+ · FastAPI · DuckDB · uv · ruff · mypy · pytest

***

## Project layout

```
my-fi/
├── app/
│   ├── main.py          # FastAPI app entry point
│   ├── api/             # Route handlers (FastAPI routers)
│   ├── core/            # Config, settings (pydantic-settings)
│   ├── db/              # DuckDB connection and query helpers
│   ├── models/          # Pydantic data models
│   ├── parsers/         # Bank statement / CSV parsers
│   ├── services/        # Business logic layer
│   └── web/             # Static / template assets
├── data/                # Local data files (do NOT commit real bank exports)
├── docs/                # Project documentation
├── storage/             # DuckDB database files (do NOT modify directly)
├── tests/               # Pytest test suite (mirrors app/ structure)
├── pyproject.toml       # Project metadata, deps, tool config
└── .env.example         # Required env vars template
```

***

## Commands

| Task | Command |
|------|---------|
| Install deps | `uv sync` |
| Run dev server | `uvicorn app.main:app --reload` |
| Run all tests | `uv run pytest` |
| Run single test | `uv run pytest tests/path/to/test_file.py::test_name -v` |
| Lint | `uv run ruff check app tests` |
| Format | `uv run ruff format app tests` |
| Type check | `uv run mypy app` |
| Coverage report | `uv run pytest --cov=app --cov-report=term-missing` |

> Tests enforce **100% coverage** (`--cov-fail-under=100`). Every new function needs a matching test.

***

## Code conventions

- **Python 3.12+** — use modern syntax: `match`, `TypeAlias`, `X | Y` unions, `type` keyword.
- **Strict typing** — all functions must have full type annotations. mypy runs in strict mode.
- **Pydantic models** in `app/models/` for all data shapes; never use raw `dict` for domain data.
- **Settings** via `pydantic-settings` in `app/core/`; read from env vars, never hardcode secrets.
- **DuckDB** access only through `app/db/`; do not import `duckdb` directly in routers or services.
- **Line length**: 100 chars (ruff enforced).
- **Quotes**: double (`"`) everywhere.
- **Imports**: isort order enforced by ruff (`I` rule set).

***

## Do NOT touch

- `storage/` — DuckDB files; never read or write these directly in code changes.
- `data/` — may contain real financial exports; never echo, log, or print contents.
- `uv.lock` — do not edit manually; update only via `uv add` / `uv sync`.
- `.env` — never create or suggest committing a real `.env` file.

***

## Testing rules

- Test files live in `tests/` mirroring `app/` (e.g. `app/services/foo.py` → `tests/services/test_foo.py`).
- Use `pytest` fixtures; avoid monkeypatching unless necessary.
- Mock external I/O (file reads, DB writes) so tests are fast and deterministic.
- Do **not** run tests against real DuckDB files in `storage/`.
- 100% coverage is required — missing branches will fail CI.

***

## Environment variables

See `.env.example` for required keys. Minimum needed to run locally:

```
DATABASE_PATH=./storage/my_fi.db
```

***

## Codex task hints

- Prefer editing **one module at a time** — state the exact file path in your request.
- When adding a new parser, touch only: `app/parsers/`, `app/models/`, and its test file.
- When adding a new API route, touch only: `app/api/`, `app/services/`, and its test file.
- Ask for a short plan before implementing anything that spans more than 2 files.