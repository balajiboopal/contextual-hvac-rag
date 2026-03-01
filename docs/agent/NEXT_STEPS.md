# NEXT_STEPS

## Ingestion

- [x] Add the PDF metadata extraction module.
- [x] Add the ingestion CLI and JSONL ingest logging.
- [x] Add sample test fixtures for PDF metadata heuristics.
- [ ] Add integration coverage against the real Contextual ingest endpoint shape.
- [ ] Add fixture PDFs for end-to-end extraction regression tests.
- [ ] Add separate `validate-env` scopes for ingest vs bot so optional variables are reported more clearly.

## Bot

- [x] Add the FastAPI WhatsApp webhook app.
- [x] Add store backends and inbound-only fee guard enforcement.
- [x] Add Meta Cloud API reply client.
- [x] Add local readiness checks and test-number setup docs.
- [x] Add fallback to the ACL query endpoint when the agent requires it.
- [x] Confirm the top-level live response shape and support nested response extraction.
- [x] Persist attribution payloads for later evaluation and normalize replies for WhatsApp display.
- [x] Improve WhatsApp formatting for malformed table-like output and broken Unicode bullets.
- [x] Convert common two-column maintenance tables into title-plus-detail chat bullets.
- [x] Add a bot-only direct ACL query mode to avoid the wasted `/query` probe request.
- [x] Add a short-lived per-user response cache for repeated identical questions.
- [x] Log and persist best-effort stage timings for the live bot query path.
- [x] Make the bot memory mode configurable so it can run stateful or stateless.
- [x] Prefer SQLite-backed local bot state in the env template for durable conversation continuity.
- [x] Split long WhatsApp replies into multiple message-safe chunks.
- [x] Add compact retrieval previews to the bot logs for faster answer-quality debugging.
- [x] Apply concise WhatsApp-oriented response guidance before querying the agent.
- [x] Make the WhatsApp style prompt opt-in after confirming it can interfere with retrieval for some grounded queries.
- [ ] Add an integration test that locks the known Contextual agent response schema.
- [ ] Add signature validation for Meta webhook requests if enabled for the app.
- [ ] Add async queueing if webhook load grows beyond simple background tasks.

## Eval

- [x] Document JSONL golden dataset format.
- [x] Add retrieval metric calculators (Recall@K, MRR, source hit rate, citation validity).
- [x] Add a CLI-ready runner to execute the golden dataset against the agent query API.
- [x] Add retrieval normalization and JSONL/JSON writers for per-query results.
- [x] Wire the new eval runner into the top-level Typer CLI.
- [x] Improve retrieval normalization for nested metadata payloads.
- [x] Align the eval output keys with explicit errors and `by_gold_sources`.
- [ ] Add a sample golden CSV fixture and an integration smoke test for the full eval command.

## Deployment

- [ ] Add deployment notes for local tunneling and future cloud hosting.
- [ ] Add CI checks for lint and tests.
- [ ] Wire remote GitHub pushes from the local machine after reviewing staged changes.
