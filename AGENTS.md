# AGENTS.md — my-fi

> Local-first personal banking ingestion engine.
> Python 3.12+ · FastAPI · DuckDB · uv · ruff · mypy · pytest

---

## Commands

```
uv sync                          # install deps
uvicorn app.main:app --reload    # dev server
uv run pytest                    # run tests (100% coverage required)
uv run ruff check app tests      # lint
uv run mypy app                  # type check
```

---

## Code conventions

- Full type annotations on all functions — mypy runs in strict mode.
- Pydantic models in `app/models/` for all domain data shapes.
- DuckDB access only through `app/db/` — never import `duckdb` directly in routers or services.
- Settings via `pydantic-settings` in `app/core/` — no hardcoded secrets.
- Line length 100, double quotes (ruff enforced).

---

## Do NOT touch

- `storage/` — DuckDB files; never read/write directly.
- `data/` — may contain real bank exports; never log or print contents.
- `uv.lock` — update only via `uv add` / `uv sync`.

---

## Task hints for Codex

- Scope each request to one file or module — state the exact path.
- New parser → touch only `app/parsers/`, `app/models/`, and its test.
- New route → touch only `app/api/`, `app/services/`, and its test.
- If a change spans more than 2 files, ask for a plan first.
