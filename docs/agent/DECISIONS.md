# DECISIONS

## WhatsApp-Only Bot

- Decision: implement only Meta's official WhatsApp Cloud API.
- Rationale: avoids Telegram scope creep and avoids BSP / Twilio markup.

## Inbound-Only Messaging

- Decision: allow replies only in response to inbound user messages.
- Rationale: keeps messaging aligned to the desired zero-cost operational policy and avoids template usage.

## Local Store Backend

- Decision: support both in-memory and SQLite stores.
- Rationale: in-memory keeps local development simple; SQLite provides a minimal persistent option without adding external infrastructure.
