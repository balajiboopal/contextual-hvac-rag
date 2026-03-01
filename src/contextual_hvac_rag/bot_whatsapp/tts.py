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
        self._indic_parler_model: Any | None = None
        self._indic_parler_tokenizer: Any | None = None

    def synthesize(self, *, text: str, language: str | None) -> SynthesizedSpeech:
        """Generate a WAV file for the supplied reply text."""

        backends = [self._settings.bot_tts_default_backend]
        fallback_backend = self._settings.bot_tts_fallback_backend
        if fallback_backend not in backends:
            backends.append(fallback_backend)

        last_error: VoiceProcessingError | None = None
        for backend in backends:
            try:
                if backend == "google_wavenet":
                    return self._synthesize_with_google_wavenet(text=text, language=language)
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

    def _synthesize_with_google_wavenet(
        self,
        *,
        text: str,
        language: str | None,
    ) -> SynthesizedSpeech:
        """Generate audio using Google Cloud Text-to-Speech WaveNet voices."""

        started_at = time.perf_counter()
        try:
            from google.cloud import texttospeech
        except ImportError as exc:
            raise VoiceProcessingError(
                "Google Cloud Text-to-Speech is not installed. Install the voice extras with "
                "`pip install -e \".[voice]\"` to enable the google_wavenet backend."
            ) from exc

        try:
            language_code, voice_name = _resolve_google_voice(
                settings=self._settings,
                detected_language=language,
            )
            client = texttospeech.TextToSpeechClient()
            input_text = text[:4500]
            response = client.synthesize_speech(
                request=texttospeech.SynthesizeSpeechRequest(
                    input=texttospeech.SynthesisInput(text=input_text),
                    voice=texttospeech.VoiceSelectionParams(
                        language_code=language_code,
                        name=voice_name,
                    ),
                    audio_config=texttospeech.AudioConfig(
                        audio_encoding=texttospeech.AudioEncoding.MP3,
                        speaking_rate=self._settings.google_tts_speaking_rate,
                    ),
                )
            )
        except Exception as exc:  # noqa: BLE001
            raise VoiceProcessingError(
                "Google WaveNet TTS failed. Ensure Google Cloud TTS is enabled and "
                "application default credentials are configured."
            ) from exc

        if not response.audio_content:
            raise VoiceProcessingError("Google WaveNet TTS did not return audio content.")

        self._settings.bot_temp_dir.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            mode="wb",
            suffix=".mp3",
            prefix="tts_google_",
            dir=self._settings.bot_temp_dir,
            delete=False,
        ) as handle:
            handle.write(response.audio_content)
            output_path = Path(handle.name)

        return SynthesizedSpeech(
            audio_path=output_path,
            backend="google_wavenet",
            latency_ms=(time.perf_counter() - started_at) * 1000.0,
        )

    def _synthesize_with_indic_parler(
        self,
        *,
        text: str,
        language: str | None,
    ) -> SynthesizedSpeech:
        """Generate audio using the Parler-TTS runtime for Indic Parler."""

        started_at = time.perf_counter()
        try:
            model, tokenizer, torch = self._load_indic_parler_runtime()
            device = torch.device("cuda" if self._settings.bot_stt_device == "cuda" else "cpu")
            description = _build_voice_description(language)
            description_inputs = tokenizer(description, return_tensors="pt")
            prompt_inputs = tokenizer(text, return_tensors="pt")

            generation = model.generate(
                input_ids=description_inputs.input_ids.to(device),
                attention_mask=description_inputs.attention_mask.to(device),
                prompt_input_ids=prompt_inputs.input_ids.to(device),
                prompt_attention_mask=prompt_inputs.attention_mask.to(device),
            )
        except Exception as exc:  # noqa: BLE001
            raise VoiceProcessingError(f"Indic Parler TTS failed: {exc}") from exc

        audio = generation.detach().cpu().numpy().squeeze()
        sampling_rate = getattr(model.config, "sampling_rate", None)
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

    def _load_indic_parler_runtime(self) -> tuple[Any, Any, Any]:
        """Load and cache the Parler-TTS model, tokenizer, and torch runtime."""

        try:
            import torch
            from parler_tts import ParlerTTSForConditionalGeneration
            from transformers import AutoTokenizer
        except ImportError as exc:
            raise VoiceProcessingError(
                "The Parler-TTS runtime is not installed. Install the voice extras with "
                "`pip install -e \".[voice]\"` to enable TTS."
            ) from exc

        if self._indic_parler_model is None or self._indic_parler_tokenizer is None:
            model_id = "ai4bharat/indic-parler-tts"
            self._indic_parler_tokenizer = AutoTokenizer.from_pretrained(model_id)
            self._indic_parler_model = ParlerTTSForConditionalGeneration.from_pretrained(model_id)
            device = torch.device("cuda" if self._settings.bot_stt_device == "cuda" else "cpu")
            self._indic_parler_model.to(device)
            self._indic_parler_model.eval()

        return self._indic_parler_model, self._indic_parler_tokenizer, torch


def _build_voice_description(language: str | None) -> str:
    """Build a generic Parler-TTS voice description for reply synthesis."""

    if language:
        return (
            f"A clear, natural, helpful voice speaking {language}. "
            "The speech is calm, conversational, and suitable for a WhatsApp voice reply."
        )
    return (
        "A clear, natural, helpful voice. "
        "The speech is calm, conversational, and suitable for a WhatsApp voice reply."
    )


def _resolve_google_voice(
    *,
    settings: Settings,
    detected_language: str | None,
) -> tuple[str, str]:
    """Resolve the Google TTS language code and WaveNet voice name."""

    language_code = settings.google_tts_language_code.strip()
    if not language_code:
        language_code = _guess_google_language_code(detected_language)

    voice_name = settings.google_tts_voice_name.strip()
    if not voice_name:
        voice_name = f"{language_code}-Wavenet-A"

    return language_code, voice_name


def _guess_google_language_code(detected_language: str | None) -> str:
    """Best-effort map a short language tag to a Google TTS language code."""

    normalized = (detected_language or "").strip().lower()
    mapping = {
        "bn": "bn-IN",
        "en": "en-IN",
        "gu": "gu-IN",
        "hi": "hi-IN",
        "kn": "kn-IN",
        "ml": "ml-IN",
        "mr": "mr-IN",
        "ta": "ta-IN",
        "te": "te-IN",
        "ur": "ur-IN",
    }
    return mapping.get(normalized, "en-IN")
