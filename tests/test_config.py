"""Configuration tests."""

from __future__ import annotations

from contextual_hvac_rag.config import Settings


def test_env_presence_reports_missing_values() -> None:
    settings = Settings(
        _env_file=None,
        contextual_api_base="https://api.contextual.ai/v1",
        bot_store_backend="memory",
    )

    presence = settings.env_presence()

    assert presence["CONTEXTUAL_API_BASE"] is True
    assert presence["CONTEXTUAL_API_KEY"] is False
    assert presence["WA_VERIFY_TOKEN"] is False


def test_bot_defaults_favor_sqlite_and_stateful_memory() -> None:
    settings = Settings(_env_file=None)

    assert settings.bot_store_backend == "sqlite"
    assert settings.bot_conversation_mode == "stateful"
