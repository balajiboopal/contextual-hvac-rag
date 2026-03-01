"""Audio conversion helpers for WhatsApp voice processing."""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

from contextual_hvac_rag.config import Settings


class AudioConversionError(RuntimeError):
    """Raised when an audio conversion step fails."""


def write_temp_audio_file(
    *,
    settings: Settings,
    data: bytes,
    suffix: str,
    prefix: str,
) -> Path:
    """Write audio bytes to a temp file and return its path."""

    settings.bot_temp_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="wb",
        suffix=suffix,
        prefix=prefix,
        dir=settings.bot_temp_dir,
        delete=False,
    ) as handle:
        handle.write(data)
        return Path(handle.name)


def convert_for_transcription(*, settings: Settings, input_path: Path) -> Path:
    """Convert inbound audio into a mono 16kHz WAV file for STT."""

    output_path = input_path.with_suffix(".transcribe.wav")
    _run_ffmpeg(
        settings=settings,
        args=[
            "-y",
            "-i",
            str(input_path),
            "-ac",
            "1",
            "-ar",
            "16000",
            str(output_path),
        ],
    )
    return output_path


def convert_for_whatsapp_voice(*, settings: Settings, input_path: Path) -> Path:
    """Convert synthesized audio into an OGG/Opus file for WhatsApp voice sends."""

    output_path = input_path.with_suffix(".ogg")
    _run_ffmpeg(
        settings=settings,
        args=[
            "-y",
            "-i",
            str(input_path),
            "-c:a",
            "libopus",
            "-b:a",
            "32k",
            str(output_path),
        ],
    )
    return output_path


def cleanup_temp_files(*paths: Path | None) -> None:
    """Best-effort cleanup of temporary audio artifacts."""

    for path in paths:
        if path is None:
            continue
        try:
            path.unlink(missing_ok=True)
        except OSError:
            continue


def _run_ffmpeg(*, settings: Settings, args: list[str]) -> None:
    """Run ffmpeg with the configured binary and raise on failure."""

    ffmpeg_binary = settings.ffmpeg_binary.strip() or "ffmpeg"
    if shutil.which(ffmpeg_binary) is None:
        raise AudioConversionError(
            f"ffmpeg binary '{ffmpeg_binary}' is not available. Install ffmpeg or update FFMPEG_BINARY."
        )

    result = subprocess.run(
        [ffmpeg_binary, *args],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise AudioConversionError(
            "ffmpeg conversion failed: "
            + (result.stderr.strip() or result.stdout.strip() or "unknown error")
        )
