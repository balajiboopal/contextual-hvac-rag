"""Application configuration loaded from environment variables."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Environment-driven application settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    contextual_api_key: SecretStr | None = None
    contextual_datastore_id: str | None = None
    contextual_agent_id: str | None = None
    contextual_api_base: str = "https://api.contextual.ai/v1"

    wa_access_token: SecretStr | None = None
    wa_phone_number_id: str | None = None
    wa_verify_token: SecretStr | None = None

    app_log_level: str = "INFO"
    bot_store_backend: Literal["memory", "sqlite"] = "sqlite"
    bot_sqlite_path: Path = Path("./data/whatsapp_bot.sqlite3")
    bot_conversation_mode: Literal["stateful", "stateless"] = "stateful"
    bot_contextual_query_mode: Literal["auto", "query", "query_acl"] = "query_acl"
    bot_enable_voice: bool = False
    bot_voice_reply_mode: Literal["audio", "text", "auto"] = "audio"
    bot_stt_model_size: str = "small"
    bot_stt_device: str = "cpu"
    bot_stt_compute_type: str = "int8"
    bot_voice_translate_to_english: bool = True
    bot_voice_translate_reply_for_tts: bool = True
    bot_tts_default_backend: Literal["indic_tts", "indic_parler", "google_wavenet"] = "indic_tts"
    bot_tts_fallback_backend: Literal["indic_tts", "indic_parler", "google_wavenet"] = "indic_parler"
    google_tts_language_code: str = ""
    google_tts_voice_name: str = ""
    google_tts_speaking_rate: float = 1.0
    bot_temp_dir: Path = Path("./data/tmp_audio")
    ffmpeg_binary: str = "ffmpeg"
    eval_contextual_query_mode: Literal["auto", "query", "query_acl"] = "query_acl"
    bot_response_cache_ttl_seconds: int = 300
    bot_reply_chunk_chars: int = 1200
    bot_retrieval_preview_count: int = 3
    bot_response_style_prompt: str = ""
    ingest_log_dir: Path = Path("./logs")

    def missing_contextual_vars(self) -> list[str]:
        """Return Contextual variables required for datastore ingestion."""

        missing: list[str] = []
        if self.contextual_api_key is None:
            missing.append("CONTEXTUAL_API_KEY")
        if not self.contextual_datastore_id:
            missing.append("CONTEXTUAL_DATASTORE_ID")
        return missing

    def missing_contextual_agent_vars(self) -> list[str]:
        """Return Contextual variables required for agent queries."""

        missing: list[str] = []
        if self.contextual_api_key is None:
            missing.append("CONTEXTUAL_API_KEY")
        if not self.contextual_agent_id:
            missing.append("CONTEXTUAL_AGENT_ID")
        return missing

    def missing_whatsapp_vars(self) -> list[str]:
        """Return required WhatsApp variables that are not configured."""

        missing: list[str] = []
        if self.wa_access_token is None:
            missing.append("WA_ACCESS_TOKEN")
        if not self.wa_phone_number_id:
            missing.append("WA_PHONE_NUMBER_ID")
        if self.wa_verify_token is None:
            missing.append("WA_VERIFY_TOKEN")
        return missing

    def env_presence(self) -> dict[str, bool]:
        """Return a map of expected environment variables to set/unset booleans."""

        return {
            "CONTEXTUAL_API_KEY": self.contextual_api_key is not None,
            "CONTEXTUAL_DATASTORE_ID": bool(self.contextual_datastore_id),
            "CONTEXTUAL_AGENT_ID": bool(self.contextual_agent_id),
            "CONTEXTUAL_API_BASE": bool(self.contextual_api_base),
            "WA_ACCESS_TOKEN": self.wa_access_token is not None,
            "WA_PHONE_NUMBER_ID": bool(self.wa_phone_number_id),
            "WA_VERIFY_TOKEN": self.wa_verify_token is not None,
        }


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached settings object."""

    return Settings()
