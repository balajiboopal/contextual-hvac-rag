"""TTS helper behavior tests."""

from __future__ import annotations

from contextual_hvac_rag.bot_whatsapp.tts import (
    _is_non_english_language,
    _normalize_language_code,
    _resolve_google_voice,
    _truncate_google_tts_input,
)
from contextual_hvac_rag.config import Settings


def test_resolve_google_voice_prefers_detected_non_english_language() -> None:
    settings = Settings(
        _env_file=None,
        google_tts_language_code="en-IN",
        google_tts_voice_name="en-IN-Wavenet-A",
    )

    language_code, voice_name = _resolve_google_voice(settings=settings, detected_language="ta")

    assert language_code == "ta-IN"
    assert voice_name == "ta-IN-Wavenet-A"


def test_resolve_google_voice_uses_defaults_for_english() -> None:
    settings = Settings(
        _env_file=None,
        google_tts_language_code="en-IN",
        google_tts_voice_name="en-IN-Wavenet-A",
    )

    language_code, voice_name = _resolve_google_voice(settings=settings, detected_language="en")

    assert language_code == "en-IN"
    assert voice_name == "en-IN-Wavenet-A"


def test_language_normalization_helpers() -> None:
    assert _normalize_language_code("ta-IN") == "ta"
    assert _normalize_language_code("TA") == "ta"
    assert _normalize_language_code(None) is None
    assert _is_non_english_language("ta") is True
    assert _is_non_english_language("en-IN") is False


def test_truncate_google_tts_input_uses_utf8_byte_limit() -> None:
    text = "தமிழ்" * 2000
    truncated = _truncate_google_tts_input(text, max_bytes=4800)

    assert len(truncated.encode("utf-8")) <= 4800
    assert truncated
