"""Text-to-speech helpers for outbound WhatsApp voice replies."""

from __future__ import annotations

import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from contextual_hvac_rag.bot_whatsapp.stt import VoiceProcessingError
from contextual_hvac_rag.config import Settings


@dataclass(frozen=True, slots=True)
class SynthesizedSpeech:
    """Structured result from TTS synthesis."""

    audio_path: Path
    backend: str
    latency_ms: float


class VoiceSynthesizer:
    """Synthesize reply audio using a configurable free-model backend."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._indic_parler_pipeline: Any | None = None

    def synthesize(self, *, text: str, language: str | None) -> SynthesizedSpeech:
        """Generate a WAV file for the supplied reply text."""

        backends = [self._settings.bot_tts_default_backend]
        fallback_backend = self._settings.bot_tts_fallback_backend
        if fallback_backend not in backends:
            backends.append(fallback_backend)

        last_error: VoiceProcessingError | None = None
        for backend in backends:
            try:
                if backend == "indic_parler":
                    return self._synthesize_with_indic_parler(text=text, language=language)
                if backend == "indic_tts":
                    raise VoiceProcessingError(
                        "Indic-TTS runtime is not wired in this initial implementation yet. "
                        "Set BOT_TTS_DEFAULT_BACKEND=indic_parler to enable synthesized voice replies now."
                    )
            except VoiceProcessingError as exc:
                last_error = exc
                continue

        raise last_error or VoiceProcessingError("No TTS backend could synthesize the reply.")

    def _synthesize_with_indic_parler(
        self,
        *,
        text: str,
        language: str | None,
    ) -> SynthesizedSpeech:
        """Generate audio using a Hugging Face text-to-audio pipeline."""

        _ = language
        started_at = time.perf_counter()
        pipeline = self._load_indic_parler_pipeline()
        try:
            result = pipeline(text)
        except Exception as exc:  # noqa: BLE001
            raise VoiceProcessingError(f"Indic Parler TTS failed: {exc}") from exc

        if not isinstance(result, dict):
            raise VoiceProcessingError("Indic Parler TTS returned an unexpected payload.")

        audio = result.get("audio")
        sampling_rate = result.get("sampling_rate")
        if audio is None or not isinstance(sampling_rate, int):
            raise VoiceProcessingError("Indic Parler TTS did not return valid audio data.")

        try:
            import soundfile as soundfile
        except ImportError as exc:
            raise VoiceProcessingError(
                "soundfile is not installed. Install the voice extras with "
                "`pip install -e \".[voice]\"` to enable TTS."
            ) from exc

        self._settings.bot_temp_dir.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            suffix=".wav",
            prefix="tts_",
            dir=self._settings.bot_temp_dir,
            delete=False,
        ) as handle:
            output_path = Path(handle.name)

        soundfile.write(output_path, audio, sampling_rate)
        return SynthesizedSpeech(
            audio_path=output_path,
            backend="indic_parler",
            latency_ms=(time.perf_counter() - started_at) * 1000.0,
        )

    def _load_indic_parler_pipeline(self) -> Any:
        if self._indic_parler_pipeline is not None:
            return self._indic_parler_pipeline

        try:
            from transformers import pipeline
        except ImportError as exc:
            raise VoiceProcessingError(
                "transformers is not installed. Install the voice extras with "
                "`pip install -e \".[voice]\"` to enable TTS."
            ) from exc

        device = 0 if self._settings.bot_stt_device == "cuda" else -1
        self._indic_parler_pipeline = pipeline(
            "text-to-audio",
            model="ai4bharat/indic-parler-tts",
            device=device,
        )
        return self._indic_parler_pipeline
