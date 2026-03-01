"""WhatsApp webhook parsing helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from contextual_hvac_rag.bot_whatsapp.guards import InboundTrigger


@dataclass(frozen=True, slots=True)
class InboundMessage:
    """Normalized inbound WhatsApp message payload."""

    message_id: str
    wa_id: str
    text: str
    timestamp: int
    message_type: str = "text"
    audio_media_id: str | None = None


def verify_webhook_token(
    *,
    mode: str | None,
    verify_token: str | None,
    challenge: str | None,
    expected_token: str,
) -> str:
    """Validate Meta webhook verification parameters."""

    if mode != "subscribe":
        raise ValueError("Invalid hub.mode for webhook verification.")
    if verify_token != expected_token:
        raise ValueError("Webhook verification token mismatch.")
    if challenge is None:
        raise ValueError("Missing hub.challenge value.")
    return challenge


def parse_inbound_messages(payload: dict[str, Any]) -> list[InboundMessage]:
    """Extract inbound WhatsApp messages from a webhook payload."""

    messages: list[InboundMessage] = []
    entries = payload.get("entry", [])
    if not isinstance(entries, list):
        return messages

    for entry in entries:
        if not isinstance(entry, dict):
            continue
        changes = entry.get("changes", [])
        if not isinstance(changes, list):
            continue
        for change in changes:
            if not isinstance(change, dict):
                continue
            value = change.get("value", {})
            if not isinstance(value, dict):
                continue
            raw_messages = value.get("messages", [])
            if not isinstance(raw_messages, list):
                continue
            for raw_message in raw_messages:
                if not isinstance(raw_message, dict):
                    continue
                message_id = raw_message.get("id")
                wa_id = raw_message.get("from")
                timestamp_raw = raw_message.get("timestamp")
                if not isinstance(message_id, str) or not isinstance(wa_id, str):
                    continue
                try:
                    timestamp = int(timestamp_raw)
                except (TypeError, ValueError):
                    continue

                message_type = raw_message.get("type", "")
                text = ""
                audio_media_id: str | None = None
                if message_type == "text":
                    text_payload = raw_message.get("text", {})
                    if isinstance(text_payload, dict):
                        text_value = text_payload.get("body", "")
                        if isinstance(text_value, str):
                            text = text_value.strip()
                elif message_type == "audio":
                    audio_payload = raw_message.get("audio", {})
                    if isinstance(audio_payload, dict):
                        raw_audio_id = audio_payload.get("id")
                        if isinstance(raw_audio_id, str) and raw_audio_id.strip():
                            audio_media_id = raw_audio_id

                messages.append(
                    InboundMessage(
                        message_id=message_id,
                        wa_id=wa_id,
                        text=text,
                        timestamp=timestamp,
                        message_type=message_type if isinstance(message_type, str) else "text",
                        audio_media_id=audio_media_id,
                    )
                )
    return messages


def to_inbound_trigger(message: InboundMessage) -> InboundTrigger:
    """Convert an inbound message into the outbound guard context."""

    return InboundTrigger(
        wa_id=message.wa_id,
        message_id=message.message_id,
        user_message_ts=message.timestamp,
    )
