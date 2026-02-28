"""Tests for WhatsApp-friendly text formatting."""

from __future__ import annotations

from contextual_hvac_rag.bot_whatsapp.formatter import format_for_whatsapp


def test_format_for_whatsapp_rewrites_markdown_tables_and_citations() -> None:
    source_text = """
    | AC Service Requirements and Steps (Follow in order, all steps are necessary):[5]() |
    | --- |
    | 1. Check voltage, current and earthing[5]() |
    | 2. Inspect for refrigerant/oil leaks[5]() |

    | Additional Critical Safety Requirements:[6]() |
    | --- |
    | ✓ Always disconnect power supply[6]() |
    | ✓ Never attempt to repair it yourself[7]() |
    """

    formatted = format_for_whatsapp(source_text)

    assert "*AC Service Requirements and Steps (Follow in order, all steps are necessary):*" in formatted
    assert "1. Check voltage, current and earthing" in formatted
    assert "- Always disconnect power supply" in formatted
    assert "[5]()" not in formatted
    assert "| --- |" not in formatted
