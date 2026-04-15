# Coding Standards

## Purpose

This document defines the engineering standards for `my-fi` before implementation starts.

These standards exist to keep the codebase easy to evolve while avoiding unnecessary tech debt in a parser-heavy FastAPI backend.

They apply to:

* feature work
* bug fixes
* refactors
* tests
* documentation that affects behavior or operating procedures

---

## Git Workflow

### Branching model

`master` is the stable branch.

After this baseline standards commit, development work should follow this rule:

* do not develop new features directly on `master`
* create a new branch from the latest `master`
* open a pull request back into `master`

Recommended branch names:

* `feature/<area>-<short-description>`
* `fix/<area>-<short-description>`
* `chore/<area>-<short-description>`
* `docs/<area>-<short-description>`

Examples:

* `feature/import-upload-api`
* `feature/hdfc-parser`
* `fix/file-hash-idempotency`
* `docs/readme-bootstrap`

### Pull request rules

Every development branch should merge through a PR, even in a single-developer workflow.

The PR is the control point for:

* reviewing scope
* validating tests and coverage
* checking maintainability
* confirming the change matches the plan

PR expectations:

* one concern per PR
* small enough to review comfortably
* clear title and summary
* linked to the implementation step it belongs to
* updated docs if the behavior or operating model changed

### Commit standards

Commits should be:

* small
* intentional
* reversible
* written in imperative mood

Preferred commit style:

* `feat(imports): add csv upload endpoint contract`
* `fix(parsers): correct hdfc debit direction mapping`
* `chore(ci): add ruff and pytest checks`
* `docs(standards): define git and quality rules`

Do not mix unrelated changes in the same commit.

### Merge policy

Preferred merge style:

* squash merge for small feature branches
* keep history readable and centered on behavior changes

Before merging:

* re-sync with `master`
* resolve conflicts on the branch
* rerun quality gates

---

## Python and FastAPI Standards

### Stack defaults

The default project stack should be:

* Python
* FastAPI
* DuckDB
* `uv` for dependency and environment management
* Pydantic for request, response, and settings models
* `pytest` for tests
* `ruff` for linting and formatting
* `mypy` for static typing

### Architectural rules

Keep the application layered and explicit.

Suggested shape:

* `api/` for FastAPI routes and request wiring
* `services/` for orchestration and business logic
* `db/` or repository layer for database access
* `parsers/` for bank-specific ingestion logic
* `validation/` for reconciliation and continuity checks
* `models/` for typed schemas and domain objects
* `core/` for settings, logging, and shared infrastructure

Rules:

* API routes stay thin
* business rules do not live in route handlers
* parser logic remains bank-specific and isolated
* validation logic stays separate from parser logic where possible
* persistence details should not leak into API models
* avoid catch-all `utils.py` files; create focused modules instead

### FastAPI-specific best practices

* use Pydantic models for all request and response contracts
* declare response models explicitly
* centralize dependency wiring instead of constructing shared services inside endpoints
* use explicit exception handling and translate domain errors into stable HTTP responses
* keep OpenAPI docs accurate so `/docs` remains a trustworthy test surface
* do not put heavy parsing or reconciliation logic directly inside route functions
* do not mix blocking file and database work into fake-async code paths; prefer explicit sync code unless there is a real async benefit

### Python code quality rules

* every new module should use type hints
* public functions and methods should have clear, stable signatures
* prefer simple datatypes and explicit models over loose dictionaries
* avoid hidden mutable global state
* use `Decimal` for money values instead of float
* keep functions focused and side effects obvious
* prefer composition over inheritance unless inheritance is clearly justified
* log useful operational facts, not sensitive raw banking data
* isolate configuration in a settings layer rather than scattering environment reads

### Data and parsing rules

Because this system handles semi-structured bank exports, the backend must stay defensive.

Rules:

* never trust raw CSV rows as valid transactions without classification
* preserve source traceability from file to raw row to canonical transaction
* keep parser versioning explicit
* treat idempotency, duplicate detection, and validation as core product behavior, not cleanup work
* suspicious data should be flagged or quarantined rather than silently accepted

---

## Tech Debt Prevention Rules

These rules are specifically intended to stop avoidable debt from entering the codebase early.

* do not introduce placeholder abstractions before they are needed
* do not build generic cross-bank parsing until repeated patterns are proven
* do not copy logic across banks without extracting a clearly justified shared helper
* do not add framework complexity unless there is a present need for it
* do not leave unexplained `TODO` comments; track concrete follow-ups in docs or issues
* refactor duplication when it becomes structural, not after it spreads across the whole codebase
* update tests and docs in the same branch when behavior changes

---

## Testing Standards

### Minimum expectations

No behavior change should merge without validation.

Expected test layers:

* unit tests for isolated parsing, normalization, fingerprinting, and validation logic
* integration tests for API flows, file storage, and DuckDB interactions
* fixture-based tests for each supported bank format

### Test design rules

* use anonymized sample CSV fixtures
* cover malformed rows and noisy exports, not only clean happy paths
* assert traceability fields where applicable
* test failure and warning states explicitly
* keep tests deterministic and local-first

---

## Code Quality and Coverage Gates

The project should be developed to SonarQube-style quality gates from the start.

If SonarQube or SonarCloud is connected later, the repository should target these standards:

* maintainability rating: `A`
* reliability rating: `A`
* security rating: `A`
* new code coverage: at least `90%`
* overall coverage: at least `85%`
* duplicated lines on new code: less than `3%`
* no blocker or critical issues on new code

Until Sonar is wired in, enforce equivalent local gates:

* `ruff check` passes
* formatting check passes
* `mypy` passes for production code
* `pytest` passes
* coverage report meets the documented thresholds

Critical modules should aim higher than the repo-wide minimum:

* parsers
* duplicate detection
* validation and reconciliation
* import orchestration

For those modules, target `90%+` coverage.

---

## Definition of Done for Development PRs

A development PR is not ready to merge unless:

* the branch is scoped to one logical change
* the code matches the implementation plan step it belongs to
* linting, typing, tests, and coverage pass
* docs are updated if the change affects behavior, setup, or operations
* API contracts remain documented in FastAPI/OpenAPI
* no avoidable duplication or shortcut introduces obvious debt

---

## First Practical Application

These standards apply starting with the first implementation branch after this baseline commit.

That means:

* this standards work can land directly on `master`
* the next engineering task should start from a new branch
* the next branch should target `P0: Bootstrap the runnable service`

