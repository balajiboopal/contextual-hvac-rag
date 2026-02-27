# AGENT_CONTEXT

## Project Summary

This repository implements a Python 3.11+ scaffold for an HVAC / technical-manual RAG workflow using Contextual AI. It covers:

- ZIP extraction for uploaded manual datasets.
- PDF metadata extraction and ingestion into a Contextual datastore.
- A WhatsApp-only support bot using Meta's official WhatsApp Cloud API.
- Placeholder evaluation assets for future retrieval benchmarking.

## Architecture

- CLI entry point: `contextual_hvac_rag.cli`
- Ingestion path: local ZIP/PDFs -> metadata extraction -> metadata flattening -> Contextual datastore ingest
- Bot path: Meta webhook -> inbound message parse -> Contextual agent query -> WhatsApp reply
- Storage for bot state: in-memory (dev) or SQLite (local prod-ish)

## Invariants / Guardrails

- No Colab-specific code.
- No hardcoded secrets. Use environment variables only.
- Local CLI usage is explicit: `unzip-dataset --zip-path ... --extract-dir ...` and `ingest-pdfs --pdf-dir ...`.
- WhatsApp is inbound-only:
  - only respond to inbound user messages
  - no proactive outbound sends
  - no template sends
  - no scheduled outbound jobs
  - if user is inactive for more than 24 hours, do not send anything until the user messages again
- Continue PDF ingestion on per-file failures and write JSONL ingest logs.

## Key Environment Variables

- `CONTEXTUAL_API_KEY`
- `CONTEXTUAL_DATASTORE_ID`
- `CONTEXTUAL_AGENT_ID`
- `CONTEXTUAL_API_BASE` (default `https://api.contextual.ai/v1`)
- `WA_ACCESS_TOKEN`
- `WA_PHONE_NUMBER_ID`
- `WA_VERIFY_TOKEN`
- `BOT_STORE_BACKEND`
- `BOT_SQLITE_PATH`
- `INGEST_LOG_DIR`

## HTTP Endpoints

- `GET /healthz`
- `POST /datastores/{DATASTORE_ID}/documents`
- `POST /agents/{AGENT_ID}/query`
- `GET /whatsapp/webhook`
- `POST /whatsapp/webhook`

## Directory Map

- `src/contextual_hvac_rag/`: application code
  - `ingest/`: unzip helper and PDF ingestion pipeline
  - `metadata/`: faithful Colab-derived PDF metadata heuristics and flattening
  - `bot_whatsapp/`: FastAPI app, webhook parsing, policy guards, Cloud API sender, and stores
- `tests/`: test suite placeholders and basic unit tests
- `eval/`: evaluation dataset planning artifacts
- `docs/agent/`: agent context, worklog, decisions, and prioritized next steps
- `docs/whatsapp_test_number_setup.md`: practical sandbox setup guide for Meta's test number
