# WORKLOG

## 2026-02-27

- Added automatic fallback from `/query` to `/query/acl` when the Contextual agent reports ACL is active.
- Fixed the Contextual agent query request shape to use `messages` instead of `message`, based on live API validation feedback.
- Added a `/healthz` endpoint for local WhatsApp bot readiness checks and a dedicated Meta test-number setup guide.
- Fixed ingestion settings validation so `ingest-pdfs` only requires datastore credentials, not `CONTEXTUAL_AGENT_ID`.
- Refined the ingestion refactor to more closely match the original Colab notebook: explicit local-path CLI flags, faithful TOC/index heuristics, and the original Contextual ingest metadata payload shape.
- Added targeted tests for TOC/index scoring and updated the metadata flattening tests for the page-hit model.
- Added the ingestion modules for ZIP extraction, PDF metadata heuristics, Contextual datastore uploads, and JSONL ingest logging.
- Added the WhatsApp FastAPI webhook app, in-memory and SQLite stores, Cloud API sender, and strict inbound-only fee guardrails.
- Added placeholder tests and the evaluation directory with sample JSONL documentation.
- Added the core Python package scaffold with settings management, logging configuration, the Contextual API client wrapper, and the Typer CLI entrypoint.
- Bootstrapped repository metadata, packaging, environment template, and top-level project documentation.
- Added the initial agent context files to keep future LLM-driven changes consistent.
