"""Tests for the WhatsApp response cache."""

from __future__ import annotations

from contextual_hvac_rag.bot_whatsapp.cache import CachedAgentResponse, ResponseCache, build_cache_key


def test_build_cache_key_normalizes_case_and_whitespace() -> None:
    key_one = build_cache_key(wa_id="123", text="  Clean   Filter  ")
    key_two = build_cache_key(wa_id="123", text="clean filter")

    assert key_one == key_two


def test_response_cache_returns_item_before_expiry_and_evicts_after() -> None:
    cache = ResponseCache(ttl_seconds=5)
    payload = CachedAgentResponse(
        answer_text="cached answer",
        attributions=[{"source": "manual.pdf"}],
        retrieval_contents=[],
    )

    cache.set("user:question", payload, now=100.0)

    assert cache.get("user:question", now=104.0) == payload
    assert cache.get("user:question", now=105.0) is None


def test_response_cache_is_disabled_when_ttl_is_zero() -> None:
    cache = ResponseCache(ttl_seconds=0)
    payload = CachedAgentResponse(
        answer_text="cached answer",
        attributions=[],
        retrieval_contents=[],
    )

    cache.set("user:question", payload, now=100.0)

    assert cache.get("user:question", now=101.0) is None
