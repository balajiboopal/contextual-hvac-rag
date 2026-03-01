"""Persistent JSONL logging for WhatsApp agent responses."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from contextual_hvac_rag.bot_whatsapp.webhook import InboundMessage
from contextual_hvac_rag.config import Settings
from contextual_hvac_rag.contextual_client import AgentQueryResult


def append_agent_event_log(
    *,
    settings: Settings,
    inbound_message: InboundMessage,
    result: AgentQueryResult,
    formatted_reply: str,
    cache_hit: bool,
    reply_chunk_count: int,
) -> Path:
    """Append a structured bot interaction record for later evaluation."""

    settings.ingest_log_dir.mkdir(parents=True, exist_ok=True)
    log_path = settings.ingest_log_dir / "whatsapp_agent_events.jsonl"
    record = {
        "logged_at_utc": datetime.now(timezone.utc).isoformat(),
        "wa_id": inbound_message.wa_id,
        "wa_message_id": inbound_message.message_id,
        "wa_message_ts": inbound_message.timestamp,
        "user_text": inbound_message.text,
        "contextual_conversation_id": result.conversation_id,
        "contextual_message_id": result.message_id,
        "raw_answer_text": result.answer_text,
        "formatted_reply_text": formatted_reply,
        "reply_chunk_count": reply_chunk_count,
        "cache_hit": cache_hit,
        "latency_ms": result.latency_ms,
        "retrieval_preview": _build_retrieval_preview(result.retrieval_contents),
        "attributions": result.attributions,
        "retrieval_contents": result.retrieval_contents,
    }
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=True) + "\n")
    return log_path


def _build_retrieval_preview(retrieval_contents: list[dict[str, object]]) -> list[dict[str, object]]:
    """Return a compact preview of the top retrieved sources for debugging."""

    preview: list[dict[str, object]] = []
    for item in retrieval_contents[:3]:
        metadata = item.get("ctxl_metadata")
        filename = None
        if isinstance(metadata, dict):
            raw_filename = metadata.get("file_name")
            if isinstance(raw_filename, str) and raw_filename.strip():
                filename = raw_filename
        if filename is None:
            raw_doc_name = item.get("doc_name")
            if isinstance(raw_doc_name, str) and raw_doc_name.strip():
                filename = raw_doc_name

        preview.append(
            {
                "filename": filename or "unknown",
                "page": item.get("page"),
                "score": item.get("score"),
            }
        )
    return preview
