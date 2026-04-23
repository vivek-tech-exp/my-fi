# Contributing to my-fi

Thanks for wanting to contribute! Here's how to get started.

## Quick Setup

```bash
# 1. Fork the repo on GitHub, then clone your fork
git clone https://github.com/<your-username>/my-fi.git
cd my-fi

# 2. Run the setup script
./setup.sh

# 3. Verify everything works
make test
make lint
```

## Making Changes

1. **Create a branch** from `master`:
   ```bash
   git checkout -b feature/your-change-name
   ```

2. **Make your changes** — keep them focused on one thing.

3. **Run the quality checks** before committing:
   ```bash
   make test    # all tests must pass (100% coverage required)
   make lint    # ruff + mypy must be clean
   ```

4. **Open a pull request** against `master`.

## Branch Naming

Use descriptive prefixes:

- `feature/` — new functionality (e.g., `feature/icici-parser`)
- `fix/` — bug fixes (e.g., `fix/date-parsing-edge-case`)
- `docs/` — documentation updates

## Code Style

- **Type annotations** on all functions (mypy strict mode)
- **Double quotes**, 100-char line length (ruff enforced)
- **Pydantic models** in `app/models/` for all data shapes
- **DuckDB access** only through `app/db/` — never import `duckdb` directly in routers or services

## Adding a New Bank Parser

If you want to add support for a new bank:

1. Create the parser in `app/parsers/<bank_name>.py`
2. Add the bank to `app/models/imports.py` (the `BankName` enum)
3. Register the parser in `app/parsers/registry.py`
4. Add a synthetic sample CSV in `samples/<bank_name>_sample.csv`
5. Write tests covering the parser

## Questions?

Open a [GitHub Issue](https://github.com/vivek-tech-exp/my-fi/issues) — happy to help.
