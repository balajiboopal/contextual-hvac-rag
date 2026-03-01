"""FastAPI application for WhatsApp webhook handling."""

from __future__ import annotations

import logging
import time
from typing import Annotated

from fastapi import BackgroundTasks, FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse, PlainTextResponse

from contextual_hvac_rag.bot_whatsapp.cache import CachedAgentResponse, ResponseCache, build_cache_key
from contextual_hvac_rag.bot_whatsapp.cloud_api import WhatsAppCloudAPI
from contextual_hvac_rag.bot_whatsapp.event_log import append_agent_event_log
from contextual_hvac_rag.bot_whatsapp.formatter import format_for_whatsapp
from contextual_hvac_rag.bot_whatsapp.guards import GuardViolation
from contextual_hvac_rag.bot_whatsapp.store import InMemoryStore, SQLiteStore, StoreProtocol
from contextual_hvac_rag.bot_whatsapp.webhook import (
    InboundMessage,
    parse_inbound_messages,
    to_inbound_trigger,
    verify_webhook_token,
)
from contextual_hvac_rag.config import Settings, get_settings
from contextual_hvac_rag.contextual_client import AgentQueryResult, ContextualClient, ContextualClientError
from contextual_hvac_rag.eval.latency import LATENCY_KEYS, extract_latency_ms
from contextual_hvac_rag.logging_config import configure_logging

LOGGER = logging.getLogger(__name__)
SETTINGS = get_settings()
configure_logging(SETTINGS.app_log_level)


def build_store(settings: Settings) -> StoreProtocol:
    """Create the configured state store backend."""

    if settings.bot_store_backend == "sqlite":
        return SQLiteStore(settings.bot_sqlite_path)
    return InMemoryStore()


STORE = build_store(SETTINGS)
CONTEXTUAL_CLIENT = ContextualClient(
    SETTINGS,
    agent_query_mode=SETTINGS.bot_contextual_query_mode,
)
RESPONSE_CACHE = ResponseCache(ttl_seconds=SETTINGS.bot_response_cache_ttl_seconds)
WHATSAPP_API = WhatsAppCloudAPI(SETTINGS)
app = FastAPI(title="Contextual HVAC WhatsApp Bot")


@app.on_event("shutdown")
def shutdown_event() -> None:
    """Release runtime resources on app shutdown."""

    STORE.close()
    CONTEXTUAL_CLIENT.close()
    WHATSAPP_API.close()


@app.get("/healthz")
def healthcheck() -> JSONResponse:
    """Return a simple readiness snapshot for local setup validation."""

    return JSONResponse(
        content={
            "status": "ok",
            "bot_store_backend": SETTINGS.bot_store_backend,
            "bot_contextual_query_mode": SETTINGS.bot_contextual_query_mode,
            "bot_response_cache_ttl_seconds": SETTINGS.bot_response_cache_ttl_seconds,
            "contextual_agent_configured": bool(SETTINGS.contextual_agent_id),
            "wa_verify_token_configured": SETTINGS.wa_verify_token is not None,
            "wa_access_token_configured": SETTINGS.wa_access_token is not None,
            "wa_phone_number_id_configured": bool(SETTINGS.wa_phone_number_id),
        }
    )


@app.get("/whatsapp/webhook")
def verify_webhook(
    hub_mode: Annotated[str | None, Query(alias="hub.mode")] = None,
    hub_verify_token: Annotated[str | None, Query(alias="hub.verify_token")] = None,
    hub_challenge: Annotated[str | None, Query(alias="hub.challenge")] = None,
) -> PlainTextResponse:
    """Handle Meta's webhook verification handshake."""

    verify_token = SETTINGS.wa_verify_token
    if verify_token is None:
        raise HTTPException(status_code=500, detail="WA_VERIFY_TOKEN is not configured.")

    try:
        challenge = verify_webhook_token(
            mode=hub_mode,
            verify_token=hub_verify_token,
            challenge=hub_challenge,
            expected_token=verify_token.get_secret_value(),
        )
    except ValueError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    return PlainTextResponse(content=challenge)


@app.post("/whatsapp/webhook")
def receive_webhook(payload: dict, background_tasks: BackgroundTasks) -> JSONResponse:
    """Accept inbound messages, dedupe them, and process replies in the background."""

    inbound_messages = parse_inbound_messages(payload)
    queued_messages: list[InboundMessage] = []
    for message in inbound_messages:
        if STORE.has_processed_message(message.message_id):
            LOGGER.info("Skipping duplicate WhatsApp message %s", message.message_id)
            continue
        STORE.mark_processed_message(message.message_id, processed_at=message.timestamp)
        queued_messages.append(message)

    if queued_messages:
        background_tasks.add_task(process_inbound_messages, queued_messages)

    return JSONResponse(
        content={"status": "accepted", "queued_messages": len(queued_messages)}
    )


def process_inbound_messages(messages: list[InboundMessage]) -> None:
    """Process inbound messages after the webhook has been acknowledged."""

    for message in messages:
        try:
            STORE.set_last_user_message_ts(message.wa_id, message.timestamp)
            if not message.text:
                LOGGER.info(
                    "Ignoring unsupported inbound message type for %s (message_id=%s)",
                    message.wa_id,
                    message.message_id,
                )
                continue

            conversation_id = STORE.get_conversation_id(message.wa_id)
            cache_key = build_cache_key(wa_id=message.wa_id, text=message.text)
            cache_started_at = time.perf_counter()
            cached_response = RESPONSE_CACHE.get(cache_key)
            cache_hit = cached_response is not None
            if cached_response is not None:
                result = _build_cached_result(
                    conversation_id=conversation_id,
                    cached_response=cached_response,
                    total_elapsed_ms=(time.perf_counter() - cache_started_at) * 1000.0,
                )
                LOGGER.info(
                    "Serving cached Contextual response for %s (cache_ttl_seconds=%s)",
                    message.wa_id,
                    SETTINGS.bot_response_cache_ttl_seconds,
                )
            else:
                result = CONTEXTUAL_CLIENT.query_agent(
                    message=message.text,
                    conversation_id=conversation_id,
                )
                if result.answer_text.strip():
                    RESPONSE_CACHE.set(
                        cache_key,
                        CachedAgentResponse(
                            answer_text=result.answer_text,
                            attributions=result.attributions,
                            retrieval_contents=result.retrieval_contents,
                        ),
                    )

            _log_agent_latencies(
                wa_id=message.wa_id,
                latency_ms=result.latency_ms,
                cache_hit=cache_hit,
            )

            if result.conversation_id and not cache_hit:
                STORE.set_conversation_id(message.wa_id, result.conversation_id)

            reply_text = format_for_whatsapp(result.answer_text)
            if not reply_text:
                reply_text = "I could not generate a response for that request."

            log_path = append_agent_event_log(
                settings=SETTINGS,
                inbound_message=message,
                result=result,
                formatted_reply=reply_text,
                cache_hit=cache_hit,
            )
            LOGGER.info(
                "Stored WhatsApp agent event for %s at %s (cache_hit=%s, attributions=%s, retrieval_contents=%s)",
                message.wa_id,
                log_path,
                cache_hit,
                len(result.attributions),
                len(result.retrieval_contents),
            )

            WHATSAPP_API.send_text_reply(
                wa_id=message.wa_id,
                text=reply_text,
                trigger=to_inbound_trigger(message),
                store=STORE,
            )
        except GuardViolation as exc:
            LOGGER.warning("Blocked WhatsApp reply for %s: %s", message.wa_id, exc)
        except ContextualClientError as exc:
            LOGGER.error("Contextual query failed for %s: %s", message.wa_id, exc)
        except Exception:  # noqa: BLE001
            LOGGER.exception("Unhandled error while processing message %s", message.message_id)


def _build_cached_result(
    *,
    conversation_id: str | None,
    cached_response: CachedAgentResponse,
    total_elapsed_ms: float,
) -> AgentQueryResult:
    """Build an AgentQueryResult-like object for cached replies."""

    return AgentQueryResult(
        status_code=200,
        conversation_id=conversation_id,
        message_id=None,
        answer_text=cached_response.answer_text,
        attributions=cached_response.attributions,
        retrieval_contents=cached_response.retrieval_contents,
        latency_ms=extract_latency_ms(payload={}, total_elapsed_ms=total_elapsed_ms),
        payload={},
    )


def _log_agent_latencies(
    *,
    wa_id: str,
    latency_ms: dict[str, float | None],
    cache_hit: bool,
) -> None:
    """Log the best-effort per-stage latencies for the bot query path."""

    rendered_parts = [
        f"{key}={latency_ms.get(key)}"
        for key in LATENCY_KEYS
    ]
    LOGGER.info(
        "Contextual timings for %s (cache_hit=%s): %s",
        wa_id,
        cache_hit,
        ", ".join(rendered_parts),
    )
