"""Directory-level PDF ingestion pipeline."""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from contextual_hvac_rag.config import get_settings
from contextual_hvac_rag.contextual_client import (
    ContextualAPIResponseError,
    ContextualClient,
    ContextualClientError,
)
from contextual_hvac_rag.metadata.extractor import extract_pdf_metadata
from contextual_hvac_rag.metadata.flatten import flatten_metadata_for_contextual

LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class IngestRecord:
    """JSONL record describing a single file ingest result."""

    filename: str
    doc_sha256: str | None
    status: str
    http_status: int | None
    contextual_document_id: str | None
    error: str | None


@dataclass(slots=True)
class IngestSummary:
    """Aggregate result for a directory ingestion run."""

    processed: int
    succeeded: int
    failed: int
    log_path: Path


def ingest_directory(*, pdf_dir: Path, source_label: str = "upload") -> IngestSummary:
    """Ingest all PDFs in a directory tree into the configured datastore."""

    if not pdf_dir.exists() or not pdf_dir.is_dir():
        raise FileNotFoundError(f"PDF directory not found: {pdf_dir}")

    settings = get_settings()
    missing = settings.missing_contextual_vars()
    if missing:
        raise ContextualClientError(
            f"Missing required Contextual settings: {', '.join(missing)}"
        )

    settings.ingest_log_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    log_path = settings.ingest_log_dir / f"ingest_{timestamp}.jsonl"
    pdf_paths = sorted(pdf_dir.rglob("*.pdf"))

    succeeded = 0
    failed = 0

    LOGGER.info("Starting ingest for %s PDF files in %s", len(pdf_paths), pdf_dir)
    with ContextualClient(settings) as client, log_path.open("a", encoding="utf-8") as log_handle:
        for pdf_path in pdf_paths:
            record = _ingest_single_pdf(
                client=client,
                pdf_path=pdf_path,
                source_label=source_label,
            )
            if record.status == "success":
                succeeded += 1
            else:
                failed += 1

            log_handle.write(json.dumps(asdict(record), ensure_ascii=True) + "\n")
            log_handle.flush()

    LOGGER.info(
        "Finished ingest run: processed=%s success=%s failed=%s log=%s",
        len(pdf_paths),
        succeeded,
        failed,
        log_path,
    )
    return IngestSummary(
        processed=len(pdf_paths),
        succeeded=succeeded,
        failed=failed,
        log_path=log_path,
    )


def _ingest_single_pdf(
    *,
    client: ContextualClient,
    pdf_path: Path,
    source_label: str,
) -> IngestRecord:
    """Ingest a single PDF and return a log-friendly result record."""

    doc_sha256: str | None = None
    try:
        file_bytes = pdf_path.read_bytes()
        metadata = extract_pdf_metadata(file_bytes, source_label=source_label)
        flattened_metadata = flatten_metadata_for_contextual(metadata)
        doc_sha256 = metadata.doc_sha256

        result = client.ingest_document(
            filename=pdf_path.name,
            file_bytes=file_bytes,
            custom_metadata=flattened_metadata,
        )
        LOGGER.info(
            "Ingested %s successfully (doc_sha256=%s, contextual_document_id=%s)",
            pdf_path.name,
            doc_sha256,
            result.document_id,
        )
        return IngestRecord(
            filename=pdf_path.name,
            doc_sha256=doc_sha256,
            status="success",
            http_status=result.status_code,
            contextual_document_id=result.document_id,
            error=None,
        )
    except ContextualAPIResponseError as exc:
        LOGGER.error("Contextual API rejected %s: %s", pdf_path.name, exc)
        return IngestRecord(
            filename=pdf_path.name,
            doc_sha256=doc_sha256,
            status="failed",
            http_status=exc.status_code,
            contextual_document_id=None,
            error=str(exc),
        )
    except Exception as exc:  # noqa: BLE001
        LOGGER.exception("Failed to ingest %s", pdf_path.name)
        return IngestRecord(
            filename=pdf_path.name,
            doc_sha256=doc_sha256,
            status="failed",
            http_status=None,
            contextual_document_id=None,
            error=str(exc),
        )
