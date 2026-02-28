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
- [ ] Confirm the exact nested `messages[*].content` schema against the live Contextual API and add an integration test.
- [ ] Add signature validation for Meta webhook requests if enabled for the app.
- [ ] Add async queueing if webhook load grows beyond simple background tasks.

## Eval

- [x] Document JSONL golden dataset format.
- [ ] Add retrieval metric calculators (Recall@K, MRR, source hit rate, citation validity).
- [ ] Add a CLI to run the golden dataset against the agent query API.

## Deployment

- [ ] Add deployment notes for local tunneling and future cloud hosting.
- [ ] Add CI checks for lint and tests.
- [ ] Wire remote GitHub pushes from the local machine after reviewing staged changes.
