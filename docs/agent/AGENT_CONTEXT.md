# AGENT_CONTEXT

## Project Summary

This repository implements a Python 3.11+ scaffold for an HVAC / technical-manual RAG workflow using Contextual AI. It covers:

- ZIP extraction for uploaded manual datasets.
- PDF metadata extraction and ingestion into a Contextual datastore.
- A WhatsApp-only support bot using Meta's official WhatsApp Cloud API.
- An offline golden-dataset evaluation pipeline for retrieval benchmarking.

## Architecture

- CLI entry point: `contextual_hvac_rag.cli`
- Ingestion path: local ZIP/PDFs -> metadata extraction -> metadata flattening -> Contextual datastore ingest
- Bot path: Meta webhook -> inbound message parse -> Contextual agent query -> WhatsApp reply
- Eval path: golden CSV -> Contextual agent query -> retrieval normalization -> metrics -> JSONL/JSON outputs
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
- Successful WhatsApp agent responses are persisted to `logs/whatsapp_agent_events.jsonl` with `attributions` and `retrieval_contents`.
- The bot uses direct `/query/acl` mode by default, a short-lived per-user response cache in stateless mode, and best-effort stage-timing logs to reduce repeated-query latency.
- Bot conversation memory is configurable: `stateful` reuses Contextual `conversation_id`, while `stateless` favors speed and cacheability.
- Evaluation is doc-wise and page-wise only. Chunk-wise metrics are intentionally not computed because no gold chunk ids exist.

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
- `BOT_CONVERSATION_MODE`
- `BOT_CONTEXTUAL_QUERY_MODE`
- `BOT_RESPONSE_CACHE_TTL_SECONDS`
- `BOT_REPLY_CHUNK_CHARS`
- `BOT_RETRIEVAL_PREVIEW_COUNT`
- `BOT_RESPONSE_STYLE_PROMPT`
- `INGEST_LOG_DIR`

## HTTP Endpoints

- `GET /healthz`
- `POST /datastores/{DATASTORE_ID}/documents`
- `POST /agents/{AGENT_ID}/query`
- `POST /agents/{AGENT_ID}/query/acl`
- `GET /whatsapp/webhook`
- `POST /whatsapp/webhook`

## Directory Map

- `src/contextual_hvac_rag/`: application code
  - `ingest/`: unzip helper and PDF ingestion pipeline
  - `metadata/`: faithful Colab-derived PDF metadata heuristics and flattening
  - `bot_whatsapp/`: FastAPI app, webhook parsing, policy guards, Cloud API sender, event logging, and reply formatting
  - `eval/`: CSV loader, retrieval normalization, metrics, latency summaries, writers, and offline runner
- `tests/`: test suite placeholders and basic unit tests
- `eval/`: evaluation dataset planning artifacts
- `docs/agent/`: agent context, worklog, decisions, and prioritized next steps
- `docs/whatsapp_test_number_setup.md`: practical sandbox setup guide for Meta's test number
