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


class FasterWhisperTranscriber:
    """Lazy wrapper around faster-whisper for transcribing audio files."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._model: Any | None = None

    def transcribe_file(self, *, audio_path: Path) -> TranscriptionResult:
        """Transcribe a WAV file into plain text."""

        started_at = time.perf_counter()
        model = self._load_model()
        try:
            segments, info = model.transcribe(
                str(audio_path),
                beam_size=1,
                vad_filter=True,
            )
        except Exception as exc:  # noqa: BLE001
            raise VoiceProcessingError(f"Voice transcription failed: {exc}") from exc

        text_parts = [segment.text.strip() for segment in segments if segment.text.strip()]
        language = getattr(info, "language", None)
        return TranscriptionResult(
            text=" ".join(text_parts).strip(),
            language=language if isinstance(language, str) and language.strip() else None,
            latency_ms=(time.perf_counter() - started_at) * 1000.0,
        )

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
