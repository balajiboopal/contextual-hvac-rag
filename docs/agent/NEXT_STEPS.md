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
- [ ] Add an integration test that locks the known Contextual agent response schema.
- [ ] Add signature validation for Meta webhook requests if enabled for the app.
- [ ] Add async queueing if webhook load grows beyond simple background tasks.

## Eval

- [x] Document JSONL golden dataset format.
- [x] Add retrieval metric calculators (Recall@K, MRR, source hit rate, citation validity).
- [x] Add a CLI-ready runner to execute the golden dataset against the agent query API.
- [x] Add retrieval normalization and JSONL/JSON writers for per-query results.
- [x] Wire the new eval runner into the top-level Typer CLI.
- [ ] Add a sample golden CSV fixture and an integration smoke test for the full eval command.

## Deployment

- [ ] Add deployment notes for local tunneling and future cloud hosting.
- [ ] Add CI checks for lint and tests.
- [ ] Wire remote GitHub pushes from the local machine after reviewing staged changes.
