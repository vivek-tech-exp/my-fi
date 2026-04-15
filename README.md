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

The first execution milestone is `P0: Bootstrap the runnable service`.
