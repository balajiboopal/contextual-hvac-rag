# Contextual HVAC Technical Docs RAG

Python 3.11+ application for building and serving an HVAC technical-document question answering system on top of Contextual AI. It includes:

- a local ingestion pipeline for PDF manuals
- a WhatsApp bot using Meta's official WhatsApp Cloud API
- an offline evaluation pipeline for golden-dataset testing

The repository is designed for local development first, with clean configuration, structured logging, and CLI workflows that are easy to run and extend.

## What This Project Does

The system follows a standard retrieval-augmented generation (RAG) workflow:

1. PDF manuals are ingested into a Contextual datastore.
2. A Contextual agent queries that datastore to retrieve relevant passages.
3. The agent generates a grounded answer using the retrieved content.
4. The answer can be used through:
   - a CLI workflow
   - the WhatsApp bot
   - the offline evaluation pipeline

In practical terms, this lets you ask questions such as service, maintenance, troubleshooting, and safety queries against your own HVAC manuals instead of relying on a general-purpose chatbot.

## Architecture

```text
PDF ZIP / PDF Folder
        |
        v
  Ingestion CLI
  unzip + parse + upload
        |
        v
Contextual Datastore
        ^
        |
Contextual Agent API
        ^
        |
FastAPI WhatsApp App  <---- Meta WhatsApp Webhook
        |
        v
Meta WhatsApp Cloud API
```

## How The Main Flows Work

### 1. Ingestion

The ingestion flow builds the knowledge base.

1. You point the CLI at a ZIP file or a directory of PDFs.
2. The app extracts PDFs locally if needed.
3. Each PDF is parsed with PyMuPDF.
4. Metadata such as title, type, date, TOC pages, and index pages is extracted.
5. Each PDF is uploaded to the Contextual datastore with `custom_metadata`.
6. A JSONL log is written with one status record per file.

This is the part that turns a folder of manuals into a searchable datastore.

### 2. WhatsApp Bot

The WhatsApp bot is a FastAPI service that receives inbound messages from Meta.

A **webhook** is simply an HTTP endpoint that another system calls when an event happens. In this project:

- a user sends a WhatsApp message
- Meta sends an HTTP request to your app
- your app processes the message and sends a reply

There are two webhook routes:

- `GET /whatsapp/webhook`
  - used for Meta verification during setup
- `POST /whatsapp/webhook`
  - used for actual inbound message delivery

For text messages, the bot:

1. receives the inbound webhook
2. parses the message
3. checks the inbound-only guardrails
4. queries the Contextual agent
5. formats the answer for WhatsApp
6. sends a reply through Meta Cloud API

The bot is intentionally designed to only respond to inbound user messages and not send proactive messages.

### 3. Evaluation

The evaluation pipeline is an offline scoring workflow for a golden CSV.

It:

1. loads a CSV of test questions and expected sources
2. queries the Contextual agent row by row
3. normalizes retrieved results
4. computes DOC-level and PAGE-level retrieval metrics
5. writes per-query and summary output files

This is the repeatable way to measure retrieval quality over time.

## Repository Layout

- `src/contextual_hvac_rag/config.py`
  Environment-based settings.
- `src/contextual_hvac_rag/contextual_client.py`
  Contextual API wrapper for datastore ingestion and agent queries.
- `src/contextual_hvac_rag/metadata/`
  PDF metadata extraction and flattening.
- `src/contextual_hvac_rag/ingest/`
  ZIP extraction and bulk PDF ingestion.
- `src/contextual_hvac_rag/bot_whatsapp/`
  WhatsApp webhook app, Meta Cloud API client, stores, guards, formatting, and optional voice support.
- `src/contextual_hvac_rag/eval/`
  Offline evaluation loader, metrics, normalization, latency aggregation, and writers.
- `eval/`
  Evaluation documentation and local outputs.
- `docs/`
  Supporting operational notes such as WhatsApp test-number setup and implementation blueprints.

## Quickstart

1. Create and activate a Python 3.11+ virtual environment.

2. Install the base dependencies:

```bash
pip install -e ".[dev]"
```

Optional voice dependencies:

```bash
pip install -e ".[dev,voice]"
```

3. Copy `.env.example` to `.env` and fill in the required values.

Minimum for ingestion:

- `CONTEXTUAL_API_KEY`
- `CONTEXTUAL_DATASTORE_ID`

Additional values for the WhatsApp bot:

- `CONTEXTUAL_AGENT_ID`
- `WA_ACCESS_TOKEN`
- `WA_PHONE_NUMBER_ID`
- `WA_VERIFY_TOKEN`

4. Validate the environment:

```bash
contextual-hvac-rag validate-env
```

## Ingestion Commands

Extract a ZIP dataset:

```bash
contextual-hvac-rag unzip-dataset --zip-path ./Eval_Dataset.zip --extract-dir ./data/pdfs
```

Ingest a directory of PDFs:

```bash
contextual-hvac-rag ingest-pdfs --pdf-dir ./data/pdfs --source-label upload
```

The ingestion run writes a JSONL log under `./logs/`.

## WhatsApp Bot Setup

Start the FastAPI app:

```bash
uvicorn contextual_hvac_rag.bot_whatsapp.app:app --host 0.0.0.0 --port 8000
```

Health check:

```bash
curl http://127.0.0.1:8000/healthz
```

For local webhook testing, expose the app with a tunnel such as `ngrok`, then use:

- `GET /whatsapp/webhook` for verification
- `POST /whatsapp/webhook` for inbound messages

For a detailed Meta sandbox setup using the WhatsApp test number, see:

- `docs/whatsapp_test_number_setup.md`

### Voice Support

Voice support is optional and still best treated as an experimental path.

Current voice path:

- inbound audio can be transcribed with `faster-whisper`
- the transcribed text is sent to the Contextual agent
- the reply can be synthesized to audio and sent back as a WhatsApp voice note

Available TTS backends:

- `google_wavenet`
  - faster managed TTS via Google Cloud Text-to-Speech
- `indic_parler`
  - local model-based TTS, slower on CPU

For faster voice replies, `google_wavenet` is the practical option, but it requires Google Cloud credentials and the Text-to-Speech API to be enabled.

## Evaluation Pipeline

Run the evaluator:

```bash
contextual-hvac-rag eval --input ./eval/golden.csv --out ./eval/results --top-k 10
```

Quick smoke test on a subset:

```bash
contextual-hvac-rag eval --input ./eval/golden.csv --out ./eval/results_smoke --top-k 10 --limit 5
```

Outputs:

- `per_query_results.jsonl`
- `summary.json`

The evaluator supports missing gold fields and skips scoring when a row does not contain enough gold data.

## Configuration Notes

Important runtime controls include:

- `BOT_CONVERSATION_MODE`
  - `stateful` for follow-up memory
  - `stateless` for lower latency and better cache reuse
- `BOT_RESPONSE_CACHE_TTL_SECONDS`
  - enables short-lived repeat-question caching in stateless mode
- `BOT_ENABLE_VOICE`
  - enables inbound audio processing
- `BOT_TTS_DEFAULT_BACKEND`
  - choose the outbound voice backend

## Troubleshooting

- `validate-env` reports missing variables
  - update `.env` and restart the shell
- webhook verification fails
  - make sure `WA_VERIFY_TOKEN` matches the value configured in Meta
- WhatsApp replies are blocked
  - the bot only replies to inbound user messages
- cache is not being used
  - cache is only active in `BOT_CONVERSATION_MODE=stateless`
- voice replies are slow
  - long replies are expensive to synthesize; managed TTS is faster than local CPU models
- PDF ingestion fails for some files
  - the ingest loop continues; inspect the JSONL log in `./logs/`

## Security

- Never commit `.env` or any real credentials.
- Rotate keys immediately if they are exposed.
- Use separate credentials for local development and deployed environments.

## Deployment

This repository is set up for local development and testing first.

Common progression:

1. run FastAPI locally
2. expose it with `ngrok` or `cloudflared`
3. validate the WhatsApp webhook flow
4. move the app to a cloud host later if you need stable uptime and lower webhook friction

Deployment manifests are not included yet.
