"""Speech-to-text helpers for inbound WhatsApp voice notes."""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from contextual_hvac_rag.config import Settings


class VoiceProcessingError(RuntimeError):
    """Raised when a voice STT/TTS step cannot complete."""


@dataclass(frozen=True, slots=True)
class TranscriptionResult:
    """Structured result from audio transcription."""

    text: str
    language: str | None
    latency_ms: float
    retrieval_text: str
    translated_text: str | None = None
    translation_latency_ms: float | None = None


class FasterWhisperTranscriber:
    """Lazy wrapper around faster-whisper for transcribing audio files."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._model: Any | None = None

    def transcribe_file(self, *, audio_path: Path) -> TranscriptionResult:
        """Transcribe a WAV file into plain text."""

        started_at = time.perf_counter()
        model = self._load_model()
        segments, info = self._run_transcribe(model=model, audio_path=audio_path, task="transcribe")
        text_parts = [segment.text.strip() for segment in segments if segment.text.strip()]
        original_text = " ".join(text_parts).strip()
        language_raw = getattr(info, "language", None)
        language = language_raw if isinstance(language_raw, str) and language_raw.strip() else None

        retrieval_text = original_text
        translated_text: str | None = None
        translation_latency_ms: float | None = None
        if (
            self._settings.bot_voice_translate_to_english
            and language is not None
            and not language.casefold().startswith("en")
        ):
            translate_started_at = time.perf_counter()
            translated_segments, _ = self._run_transcribe(
                model=model,
                audio_path=audio_path,
                task="translate",
                language=language,
            )
            translated_parts = [
                segment.text.strip()
                for segment in translated_segments
                if segment.text.strip()
            ]
            translated_text = " ".join(translated_parts).strip()
            translation_latency_ms = (time.perf_counter() - translate_started_at) * 1000.0
            if translated_text:
                retrieval_text = translated_text

        return TranscriptionResult(
            text=original_text,
            retrieval_text=retrieval_text,
            translated_text=translated_text,
            language=language,
            latency_ms=(time.perf_counter() - started_at) * 1000.0,
            translation_latency_ms=translation_latency_ms,
        )

    def _run_transcribe(
        self,
        *,
        model: Any,
        audio_path: Path,
        task: str,
        language: str | None = None,
    ) -> tuple[Any, Any]:
        """Execute a faster-whisper transcription task and return raw segments/info."""

        try:
            kwargs: dict[str, object] = {
                "beam_size": 1,
                "vad_filter": True,
                "task": task,
            }
            if language:
                kwargs["language"] = language
            segments, info = model.transcribe(str(audio_path), **kwargs)
            return segments, info
        except Exception as exc:  # noqa: BLE001
            raise VoiceProcessingError(f"Voice transcription failed ({task}): {exc}") from exc

    def _load_model(self) -> Any:
        if self._model is not None:
            return self._model

        try:
            from faster_whisper import WhisperModel
        except ImportError as exc:
            raise VoiceProcessingError(
                "faster-whisper is not installed. Install the voice extras with "
                "`pip install -e \".[voice]\"` to enable STT."
            ) from exc

        self._model = WhisperModel(
            self._settings.bot_stt_model_size,
            device=self._settings.bot_stt_device,
            compute_type=self._settings.bot_stt_compute_type,
        )
        return self._model
