"""FastAPI application for WhatsApp webhook handling."""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Annotated

from fastapi import BackgroundTasks, FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse, PlainTextResponse

from contextual_hvac_rag.bot_whatsapp.audio_convert import (
    AudioConversionError,
    cleanup_temp_files,
    convert_for_transcription,
    convert_for_whatsapp_voice,
    write_temp_audio_file,
)
from contextual_hvac_rag.bot_whatsapp.cache import CachedAgentResponse, ResponseCache, build_cache_key
from contextual_hvac_rag.bot_whatsapp.cloud_api import WhatsAppCloudAPI
from contextual_hvac_rag.bot_whatsapp.event_log import append_agent_event_log
from contextual_hvac_rag.bot_whatsapp.formatter import format_reply_chunks
from contextual_hvac_rag.bot_whatsapp.guards import GuardViolation
from contextual_hvac_rag.bot_whatsapp.media import MediaTransferError, WhatsAppMediaClient
from contextual_hvac_rag.bot_whatsapp.store import InMemoryStore, SQLiteStore, StoreProtocol
from contextual_hvac_rag.bot_whatsapp.stt import FasterWhisperTranscriber, VoiceProcessingError
from contextual_hvac_rag.bot_whatsapp.tts import SynthesizedSpeech, VoiceSynthesizer
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
MEDIA_CLIENT = WhatsAppMediaClient(SETTINGS)
VOICE_TRANSCRIBER = FasterWhisperTranscriber(SETTINGS)
VOICE_SYNTHESIZER = VoiceSynthesizer(SETTINGS)
app = FastAPI(title="Contextual HVAC WhatsApp Bot")


@app.on_event("shutdown")
def shutdown_event() -> None:
    """Release runtime resources on app shutdown."""

    STORE.close()
    CONTEXTUAL_CLIENT.close()
    WHATSAPP_API.close()
    MEDIA_CLIENT.close()


@app.get("/healthz")
def healthcheck() -> JSONResponse:
    """Return a simple readiness snapshot for local setup validation."""

    cache_stats = RESPONSE_CACHE.stats()

    return JSONResponse(
        content={
            "status": "ok",
            "bot_store_backend": SETTINGS.bot_store_backend,
            "bot_conversation_mode": SETTINGS.bot_conversation_mode,
            "bot_contextual_query_mode": SETTINGS.bot_contextual_query_mode,
            "bot_enable_voice": SETTINGS.bot_enable_voice,
            "bot_voice_reply_mode": SETTINGS.bot_voice_reply_mode,
            "bot_response_cache_ttl_seconds": SETTINGS.bot_response_cache_ttl_seconds,
            "bot_reply_chunk_chars": SETTINGS.bot_reply_chunk_chars,
            "bot_cache_enabled": _is_cache_enabled(),
            "bot_cache_entries": cache_stats["entries"],
            "bot_cache_hits": cache_stats["hits"],
            "bot_cache_misses": cache_stats["misses"],
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
            if message.message_type == "audio":
                if not SETTINGS.bot_enable_voice:
                    LOGGER.info(
                        "Ignoring inbound audio message for %s because voice support is disabled.",
                        message.wa_id,
                    )
                    continue
                _process_audio_message(message)
                continue

            if not message.text:
                LOGGER.info(
                    "Ignoring unsupported inbound message type for %s (message_id=%s)",
                    message.wa_id,
                    message.message_id,
                )
                continue

            result, cache_hit = _query_text_request(
                wa_id=message.wa_id,
                user_text=message.text,
            )
            _log_and_send_text_reply(
                message=message,
                result=result,
                cache_hit=cache_hit,
                user_text=message.text,
            )
        except GuardViolation as exc:
            LOGGER.warning("Blocked WhatsApp reply for %s: %s", message.wa_id, exc)
        except ContextualClientError as exc:
            LOGGER.error("Contextual query failed for %s: %s", message.wa_id, exc)
        except (AudioConversionError, MediaTransferError, VoiceProcessingError) as exc:
            LOGGER.warning("Voice processing failed for %s: %s", message.wa_id, exc)
            _send_voice_failure_fallback(message)
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


def _query_text_request(
    *,
    wa_id: str,
    user_text: str,
    response_language: str | None = None,
) -> tuple[AgentQueryResult, bool]:
    """Query Contextual for a user text request, optionally using the cache."""

    conversation_id = _get_conversation_id_for_message(wa_id)
    cache_enabled = _is_cache_enabled()
    cache_text = user_text if response_language is None else f"{user_text}\n__response_language={response_language}"
    cache_key = build_cache_key(wa_id=wa_id, text=cache_text) if cache_enabled else ""
    cache_started_at = time.perf_counter()
    cached_response = RESPONSE_CACHE.get(cache_key) if cache_enabled else None
    cache_hit = cached_response is not None
    if cached_response is not None:
        result = _build_cached_result(
            conversation_id=conversation_id,
            cached_response=cached_response,
            total_elapsed_ms=(time.perf_counter() - cache_started_at) * 1000.0,
        )
        LOGGER.info(
            "Serving cached Contextual response for %s (cache_ttl_seconds=%s)",
            wa_id,
            SETTINGS.bot_response_cache_ttl_seconds,
        )
        return result, True

    system_prompt = _build_system_prompt(
        base_prompt=SETTINGS.bot_response_style_prompt,
        response_language=response_language,
    )
    result = CONTEXTUAL_CLIENT.query_agent(
        message=user_text,
        conversation_id=conversation_id,
        system_prompt=system_prompt,
    )
    if cache_enabled and result.answer_text.strip():
        RESPONSE_CACHE.set(
            cache_key,
            CachedAgentResponse(
                answer_text=result.answer_text,
                attributions=result.attributions,
                retrieval_contents=result.retrieval_contents,
            ),
        )
    return result, False


def _process_audio_message(message: InboundMessage) -> None:
    """Process a voice note via STT, Contextual, and optional TTS."""

    if not message.audio_media_id:
        raise VoiceProcessingError("Inbound audio message did not include a media id.")

    raw_audio_path: Path | None = None
    transcription_input_path: Path | None = None
    synthesized_wav_path: Path | None = None
    voice_note_path: Path | None = None

    try:
        audio_bytes, content_type = MEDIA_CLIENT.download_media(media_id=message.audio_media_id)
        raw_audio_path = write_temp_audio_file(
            settings=SETTINGS,
            data=audio_bytes,
            suffix=_guess_audio_suffix(content_type),
            prefix="wa_in_",
        )
        transcription_input_path = convert_for_transcription(
            settings=SETTINGS,
            input_path=raw_audio_path,
        )
        transcription = VOICE_TRANSCRIBER.transcribe_file(audio_path=transcription_input_path)
        if not transcription.text:
            _send_voice_failure_fallback(
                message,
                custom_text="I could not transcribe that voice note clearly. Please try a shorter or clearer recording.",
            )
            return

        LOGGER.info(
            "Transcribed WhatsApp audio for %s in %.2f ms (language=%s, chars=%s, translated_chars=%s, translation_ms=%s)",
            message.wa_id,
            transcription.latency_ms,
            transcription.language or "unknown",
            len(transcription.text),
            len(transcription.translated_text or ""),
            transcription.translation_latency_ms,
        )

        result, cache_hit = _query_text_request(
            wa_id=message.wa_id,
            user_text=transcription.retrieval_text,
            response_language=transcription.language,
        )
        _log_retrieval_preview(
            wa_id=message.wa_id,
            retrieval_contents=result.retrieval_contents,
        )
        _log_agent_latencies(
            wa_id=message.wa_id,
            latency_ms=result.latency_ms,
            cache_hit=cache_hit,
        )
        if result.conversation_id and not cache_hit and SETTINGS.bot_conversation_mode == "stateful":
            STORE.set_conversation_id(message.wa_id, result.conversation_id)

        formatted_reply = _format_single_reply(
            wa_id=message.wa_id,
            answer_text=result.answer_text,
        )
        if _should_send_voice_reply():
            try:
                synthesized = VOICE_SYNTHESIZER.synthesize(
                    text=formatted_reply,
                    language=transcription.language,
                )
                synthesized_wav_path = synthesized.audio_path
                voice_note_path = convert_for_whatsapp_voice(
                    settings=SETTINGS,
                    input_path=synthesized_wav_path,
                )
                uploaded_media_id = MEDIA_CLIENT.upload_audio(audio_path=voice_note_path)

                log_path = append_agent_event_log(
                    settings=SETTINGS,
                    inbound_message=message,
                    result=result,
                    formatted_reply=formatted_reply,
                    cache_hit=cache_hit,
                    reply_chunk_count=1,
                    user_text_override=transcription.text,
                    retrieval_query_text=transcription.retrieval_text,
                    reply_mode="audio",
                    detected_language=transcription.language,
                )
                LOGGER.info(
                    "Stored WhatsApp agent event for %s at %s (cache_hit=%s, reply_mode=audio, attributions=%s, retrieval_contents=%s, tts_ms=%.2f)",
                    message.wa_id,
                    log_path,
                    cache_hit,
                    len(result.attributions),
                    len(result.retrieval_contents),
                    synthesized.latency_ms,
                )

                WHATSAPP_API.send_audio_reply(
                    wa_id=message.wa_id,
                    media_id=uploaded_media_id,
                    trigger=to_inbound_trigger(message),
                    store=STORE,
                )
                return
            except (AudioConversionError, MediaTransferError, VoiceProcessingError) as exc:
                LOGGER.warning(
                    "Falling back to text reply for %s after voice synthesis failure: %s",
                    message.wa_id,
                    exc,
                )

        _log_and_send_text_reply(
            message=message,
            result=result,
            cache_hit=cache_hit,
            user_text=transcription.text,
            retrieval_query_text=transcription.retrieval_text,
            detected_language=transcription.language,
            already_logged=True,
        )
    finally:
        cleanup_temp_files(raw_audio_path, transcription_input_path, synthesized_wav_path, voice_note_path)


def _log_and_send_text_reply(
    *,
    message: InboundMessage,
    result: AgentQueryResult,
    cache_hit: bool,
    user_text: str,
    retrieval_query_text: str | None = None,
    detected_language: str | None = None,
    already_logged: bool = False,
) -> None:
    """Log a response and send it as a single text message."""

    if not already_logged:
        _log_retrieval_preview(
            wa_id=message.wa_id,
            retrieval_contents=result.retrieval_contents,
        )
        _log_agent_latencies(
            wa_id=message.wa_id,
            latency_ms=result.latency_ms,
            cache_hit=cache_hit,
        )

    if result.conversation_id and not cache_hit and SETTINGS.bot_conversation_mode == "stateful":
        STORE.set_conversation_id(message.wa_id, result.conversation_id)

    formatted_reply = _format_single_reply(
        wa_id=message.wa_id,
        answer_text=result.answer_text,
    )

    log_path = append_agent_event_log(
        settings=SETTINGS,
        inbound_message=message,
        result=result,
        formatted_reply=formatted_reply,
        cache_hit=cache_hit,
        reply_chunk_count=1,
        user_text_override=user_text,
        retrieval_query_text=retrieval_query_text if retrieval_query_text is not None else user_text,
        reply_mode="text",
        detected_language=detected_language,
    )
    LOGGER.info(
        "Stored WhatsApp agent event for %s at %s (cache_hit=%s, reply_mode=text, attributions=%s, retrieval_contents=%s)",
        message.wa_id,
        log_path,
        cache_hit,
        len(result.attributions),
        len(result.retrieval_contents),
    )

    WHATSAPP_API.send_text_reply(
        wa_id=message.wa_id,
        text=formatted_reply,
        trigger=to_inbound_trigger(message),
        store=STORE,
    )


def _format_single_reply(*, wa_id: str, answer_text: str) -> str:
    """Format an answer into a single WhatsApp-friendly text payload."""

    reply_segments = format_reply_chunks(
        answer_text,
        max_chars=SETTINGS.bot_reply_chunk_chars,
    )
    if not reply_segments:
        reply_segments = ["I could not generate a response for that request."]
    if len(reply_segments) > 1:
        LOGGER.info(
            "Collapsing %s formatted reply segments into one WhatsApp message for %s",
            len(reply_segments),
            wa_id,
        )
    return "\n\n".join(reply_segments)


def _send_voice_failure_fallback(
    message: InboundMessage,
    *,
    custom_text: str | None = None,
) -> None:
    """Send a text fallback when voice processing cannot complete."""

    WHATSAPP_API.send_text_reply(
        wa_id=message.wa_id,
        text=custom_text or (
            "I could not process that voice note. Please try again or send the question as text."
        ),
        trigger=to_inbound_trigger(message),
        store=STORE,
    )


def _guess_audio_suffix(content_type: str | None) -> str:
    """Infer a file suffix from the media content type."""

    if not content_type:
        return ".bin"
    normalized = content_type.casefold()
    if "ogg" in normalized:
        return ".ogg"
    if "mpeg" in normalized or "mp3" in normalized:
        return ".mp3"
    if "wav" in normalized or "wave" in normalized:
        return ".wav"
    if "mp4" in normalized or "m4a" in normalized:
        return ".m4a"
    return ".bin"


def _should_send_voice_reply() -> bool:
    """Return whether the bot should attempt an audio reply."""

    return SETTINGS.bot_voice_reply_mode in {"audio", "auto"}


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


def _get_conversation_id_for_message(wa_id: str) -> str | None:
    """Return the conversation id only when stateful memory is enabled."""

    if SETTINGS.bot_conversation_mode != "stateful":
        return None
    return STORE.get_conversation_id(wa_id)


def _is_cache_enabled() -> bool:
    """Return whether the latency cache is active for the current bot mode."""

    return (
        SETTINGS.bot_conversation_mode == "stateless"
        and SETTINGS.bot_response_cache_ttl_seconds > 0
    )


def _log_retrieval_preview(
    *,
    wa_id: str,
    retrieval_contents: list[dict[str, object]],
) -> None:
    """Log a compact retrieval preview for faster debugging of answer quality."""

    if not retrieval_contents:
        LOGGER.info("No retrieval contents returned for %s", wa_id)
        return

    preview_count = max(1, SETTINGS.bot_retrieval_preview_count)
    preview_items: list[str] = []
    for item in retrieval_contents[:preview_count]:
        filename = _extract_retrieval_filename(item)
        page = item.get("page")
        score = item.get("score")
        preview_items.append(
            f"{filename}@p{page if page is not None else '?'} (score={score})"
        )

    LOGGER.info(
        "Top retrievals for %s: %s",
        wa_id,
        "; ".join(preview_items),
    )


def _extract_retrieval_filename(item: dict[str, object]) -> str:
    """Return the most useful filename-like label for a retrieval item."""

    metadata = item.get("ctxl_metadata")
    if isinstance(metadata, dict):
        file_name = metadata.get("file_name")
        if isinstance(file_name, str) and file_name.strip():
            return file_name

    doc_name = item.get("doc_name")
    if isinstance(doc_name, str) and doc_name.strip():
        return doc_name

    content_id = item.get("content_id")
    if isinstance(content_id, str) and content_id.strip():
        return content_id

    return "unknown"


def _build_system_prompt(*, base_prompt: str, response_language: str | None) -> str:
    """Build a merged system prompt with an optional forced response language."""

    prompt_parts: list[str] = []
    base_clean = base_prompt.strip()
    if base_clean:
        prompt_parts.append(base_clean)

    if response_language and not response_language.casefold().startswith("en"):
        language_label = _language_label_from_code(response_language)
        prompt_parts.append(
            f"Answer in {language_label} only. Do not switch to English unless the user explicitly asks for English."
        )

    return "\n\n".join(prompt_parts).strip()


def _language_label_from_code(language_code: str) -> str:
    """Return a user-friendly language name from a short language code."""

    normalized = language_code.strip().casefold()
    mapping = {
        "bn": "Bengali",
        "en": "English",
        "gu": "Gujarati",
        "hi": "Hindi",
        "kn": "Kannada",
        "ml": "Malayalam",
        "mr": "Marathi",
        "ta": "Tamil",
        "te": "Telugu",
        "ur": "Urdu",
    }
    return mapping.get(normalized, normalized)
