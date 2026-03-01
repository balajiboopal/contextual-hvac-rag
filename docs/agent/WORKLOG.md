# WORKLOG

## 2026-02-27

- Added the first additive voice implementation slice: eval-result outputs are ignored in git, inbound audio is parsed, voice settings are configurable, STT/TTS/media helper modules are in place, and audio requests now fall back to text safely when voice processing fails.
- Added a reusable voice-pipeline blueprint and copy-paste agent prompt covering free-model STT/TTS, Indian language support, and a staged WhatsApp voice rollout plan.
- Added a reusable markdown blueprint and a copy-paste agent prompt so the exact evaluation pipeline can be recreated in the open-source variant of this project.
- Set the evaluation pipeline to use direct ACL agent queries by default and added explicit metric notes clarifying that page nDCG gives partial credit for correct-document/wrong-page retrievals.
- Updated the evaluation runner to skip DOC/PAGE scoring for rows with missing gold fields, added a `--limit` smoke-test option, and documented the unrated-row behavior.
- Suppressed generic table-label artifacts like `Step`, `Action`, and `Specific Details`, normalized isolated numeric step markers, and cleaned square-bullet glyphs in WhatsApp replies.
- Fixed the WhatsApp formatter to strip malformed numeric citation remnants like `1()` and `¹()` that were leaking into final replies.
- Changed the WhatsApp reply path back to a single outbound message per user query, collapsing any internal formatting segments before sending.
- Disabled the WhatsApp bot's style prompt by default after it was shown to interfere with grounded retrieval for otherwise valid datastore queries.
- Added configurable stateful/stateless bot memory, SQLite-first local defaults, WhatsApp reply chunking, richer retrieval previews, and a concise-response style prompt for better latency and UX.
- Added a bot-only direct ACL query mode, a short-lived per-user response cache, and structured live stage-timing logs to cut repeated-query latency.
- Added a targeted formatter rule that rewrites two-column maintenance tables into WhatsApp-style bullets with title and detail lines.
- Improved WhatsApp reply formatting to better handle malformed table rows, mojibake bullets, and heading spacing so chat output reads more naturally.
- Aligned evaluation output keys with the requested schema by adding explicit error fields and a `by_gold_sources` summary map.
- Hardened evaluation retrieval normalization to search nested metadata fields and added unit coverage for that payload shape.
- Wired the evaluation pipeline into the top-level CLI and replaced the eval placeholder docs with runnable instructions and metric definitions.
- Added the evaluation runner, retrieval normalization, JSON writers, and offline summary generation against a golden CSV dataset.
- Added the core evaluation primitives: golden CSV loading, page-range parsing, retrieval metrics, latency aggregation, and unit tests.
- Added WhatsApp-friendly response formatting and persistent JSONL logging of `attributions` / `retrieval_contents` for later evaluation.
- Updated agent response parsing to extract answer text from the live Contextual payload shape (`outputs.response` and `message.content`).
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
