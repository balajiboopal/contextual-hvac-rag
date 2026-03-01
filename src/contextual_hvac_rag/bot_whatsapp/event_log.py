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
        "cache_hit": cache_hit,
        "latency_ms": result.latency_ms,
        "attributions": result.attributions,
        "retrieval_contents": result.retrieval_contents,
    }
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=True) + "\n")
    return log_path
