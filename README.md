# Contextual HVAC Technical Docs RAG

Production-ready Python 3.11+ scaffold for ingesting HVAC and technical PDF manuals into Contextual AI, with a WhatsApp-only inbound support bot built on Meta's official WhatsApp Cloud API.

## Quickstart

1. Create and activate a Python 3.11+ virtual environment.
2. Install dependencies:

   ```bash
   pip install -e ".[dev]"
   ```

3. Copy `.env.example` to `.env` and fill in required values:

   - `CONTEXTUAL_API_KEY`
   - `CONTEXTUAL_DATASTORE_ID`
   - optional `CONTEXTUAL_API_BASE` (defaults to `https://api.contextual.ai/v1`)
4. Validate environment setup:

   ```bash
   contextual-hvac-rag validate-env
   ```

5. Run ingestion:

   ```bash
   contextual-hvac-rag ingest-pdfs --pdf-dir ./path/to/pdfs
   ```

6. Run the WhatsApp webhook app locally:

   ```bash
   uvicorn contextual_hvac_rag.bot_whatsapp.app:app --reload
   ```

## Architecture

```text
                +-----------------------+
                |   Local PDF Corpus    |
                |   ZIP / PDF folder    |
                +-----------+-----------+
                            |
                            v
               +------------+-------------+
               |  Ingestion CLI (Typer)   |
               | unzip + metadata + logs  |
               +------------+-------------+
                            |
                            v
               +------------+-------------+
               | Contextual API Client    |
               | datastore ingest         |
               +------------+-------------+
                            |
                            v
               +------------+-------------+
               | Contextual Datastore     |
               +------------+-------------+
                            ^
                            |
       +--------------------+--------------------+
       |                                         |
       v                                         |
+------+-----------------+           +-----------+-----------+
| WhatsApp Cloud Webhook |           | Contextual Agent API  |
| FastAPI + fee guards   +-----------> query + conversation  |
+------+-----------------+           +-----------+-----------+
       |                                         |
       v                                         |
+------+-----------------+                       |
| WhatsApp Cloud API     |<----------------------+
| inbound-only replies   |
+------------------------+
```

## Modules Overview

- `src/contextual_hvac_rag/config.py`: environment-based settings via Pydantic.
- `src/contextual_hvac_rag/contextual_client.py`: Contextual datastore ingest and agent query wrapper.
- `src/contextual_hvac_rag/metadata/`: PDF metadata extraction and metadata flattening.
- `src/contextual_hvac_rag/ingest/`: unzip helper and PDF ingestion pipeline.
- `src/contextual_hvac_rag/bot_whatsapp/`: FastAPI webhook, stores, guardrails, and Meta Cloud API sender.
- `src/contextual_hvac_rag/cli.py`: Typer entry point.
- `eval/`: placeholder evaluation dataset docs and sample JSONL.
- `docs/agent/`: source-of-truth docs for future agent-assisted changes.

## Local Run Instructions

### Ingest a ZIP archive

```bash
contextual-hvac-rag unzip-dataset --zip-path ./Eval_Dataset.zip --extract-dir ./data/eval_dataset
```

### Ingest a PDF directory

```bash
contextual-hvac-rag ingest-pdfs --pdf-dir ./data/manuals --source-label upload
```

### Start the webhook

```bash
uvicorn contextual_hvac_rag.bot_whatsapp.app:app --host 0.0.0.0 --port 8000
```

Configure your Meta webhook verification callback to `GET /whatsapp/webhook` and message delivery to `POST /whatsapp/webhook`.

Validate local bot readiness before configuring Meta:

```bash
curl http://127.0.0.1:8000/healthz
```

For a step-by-step Meta sandbox setup using the WhatsApp test number, see `docs/whatsapp_test_number_setup.md`.

## Troubleshooting

- `validate-env` reports missing variables: update `.env` and restart the shell.
- PDF parsing fails on some manuals: confirm the files are valid PDFs and retry; ingestion continues per-file on errors.
- WhatsApp replies are blocked: the fee guard only allows replies in direct response to inbound user messages.
- Webhook verification fails: ensure `WA_VERIFY_TOKEN` matches the token configured in the Meta developer console.
- SQLite store path errors: create the parent directory or set `BOT_SQLITE_PATH` to a writable location.
- `/healthz` shows `*_configured: false`: fill in the missing WhatsApp or Contextual bot variables in `.env` and restart the app.

## Migration Notes From Colab To Local

- Changed: `google.colab.files.upload()` is removed. Use `--zip-path` and `--extract-dir` for local ZIP extraction, or `--pdf-dir` when PDFs are already extracted.
- Changed: hardcoded Contextual credentials are removed. Use `.env` or exported environment variables.
- Stayed the same: PDF metadata heuristics are preserved, including SHA-256 document ids, TOC dot-leader detection, back-page index scanning, and contact/imprint false-positive filtering.
- Stayed the same: each PDF is uploaded with `custom_metadata` in the Contextual ingest request.
- Local run path: unzip first if needed, then run `ingest-pdfs`, and inspect the JSONL log written under `./logs`.

## Safety / Secrets

- Never commit `.env` or real API keys.
- If any key is exposed, rotate it immediately in the relevant provider console.
- Use distinct credentials for local development and production.

## Deployment Note

Two supported paths:

1. Local development: run FastAPI locally and expose it with `ngrok` or `cloudflared` for webhook testing.
2. Cloud deployment later: deploy the FastAPI app to a managed service and keep the same webhook contract.

This repository does not implement deployment infrastructure yet.

## Agent Workflow

- When asking an LLM agent to make changes, paste `docs/agent/AGENT_CONTEXT.md` at the top of the prompt.
- Whenever a non-trivial feature is completed, update `docs/agent/WORKLOG.md` and `docs/agent/NEXT_STEPS.md` in the same commit or PR.
- Every meaningful change should follow the commit prefixes: `feat:`, `fix:`, `refactor:`, `docs:`, `chore:`, `test:`.

## Git Workflow

For any meaningful multi-file change, the agent should provide these exact commands and should never claim it already pushed:

```bash
git status
git add <paths>
git commit -m "<type>(<scope>): message"
git push
```

## Next Steps

- Build the structured evaluation pipeline around JSONL golden datasets.
- Add deployment manifests once hosting is chosen.
- Add integration tests against a staging Contextual datastore and WhatsApp sandbox.
