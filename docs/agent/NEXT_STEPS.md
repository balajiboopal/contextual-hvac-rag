# NEXT_STEPS

## Ingestion

- [x] Add the PDF metadata extraction module.
- [x] Add the ingestion CLI and JSONL ingest logging.
- [ ] Add sample test fixtures for PDF metadata heuristics.
- [ ] Add integration coverage against the real Contextual ingest endpoint shape.

## Bot

- [x] Add the FastAPI WhatsApp webhook app.
- [x] Add store backends and inbound-only fee guard enforcement.
- [x] Add Meta Cloud API reply client.
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
