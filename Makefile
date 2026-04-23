.PHONY: help setup run test lint clean clean-cache

DATA_HOME := $(HOME)/.my-fi

help: ## Show this help message
	@echo ""
	@echo "  my-fi — available commands"
	@echo "  ─────────────────────────────────────────"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[1m%-16s\033[0m %s\n", $$1, $$2}'
	@echo ""

setup: ## Install everything (first-time setup)
	@chmod +x setup.sh && ./setup.sh

run: ## Start the local API server
	@uv run uvicorn app.main:app --reload

test: ## Run the test suite
	@uv run pytest

lint: ## Run linter and type checker
	@uv run ruff check .
	@uv run ruff format --check .
	@uv run mypy app

clean: ## Delete all data in ~/.my-fi (asks for confirmation)
	@echo ""
	@echo "  This will delete ALL data at $(DATA_HOME):"
	@echo "    - Uploaded bank CSVs"
	@echo "    - DuckDB database"
	@echo "    - Import logs"
	@echo ""
	@printf "  Are you sure? [y/N] " && read ans && [ "$$ans" = "y" ] || (echo "  Cancelled." && exit 1)
	@rm -rf $(DATA_HOME)/data $(DATA_HOME)/storage
	@echo ""
	@echo "  ✓ Data wiped. Run 'make setup' to re-create directories."
	@echo ""

clean-cache: ## Delete regeneratable caches (mypy, ruff, pytest, coverage)
	@rm -rf .mypy_cache .pytest_cache .ruff_cache .playwright-cli
	@rm -f .coverage coverage.xml
	@echo "  ✓ Caches cleared. They will regenerate on next run."
