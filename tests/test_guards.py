"""Guardrail tests."""

from __future__ import annotations

import pytest

from contextual_hvac_rag.bot_whatsapp.guards import (
    GuardViolation,
    InboundTrigger,
    ensure_inbound_reply_allowed,
)
from contextual_hvac_rag.bot_whatsapp.store import InMemoryStore


def test_inbound_reply_requires_trigger() -> None:
    store = InMemoryStore()

    with pytest.raises(GuardViolation):
        ensure_inbound_reply_allowed(trigger=None, store=store)


def test_inbound_reply_blocks_stale_trigger() -> None:
    store = InMemoryStore()
    store.set_last_user_message_ts("12345", 100)
    trigger = InboundTrigger(wa_id="12345", message_id="mid-1", user_message_ts=100)

    with pytest.raises(GuardViolation):
        ensure_inbound_reply_allowed(trigger=trigger, store=store, now_ts=100 + (24 * 60 * 60) + 1)


def test_inbound_reply_allows_recent_trigger() -> None:
    store = InMemoryStore()
    store.set_last_user_message_ts("12345", 200)
    trigger = InboundTrigger(wa_id="12345", message_id="mid-1", user_message_ts=200)

    ensure_inbound_reply_allowed(trigger=trigger, store=store, now_ts=250)

