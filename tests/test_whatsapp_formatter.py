"""Tests for WhatsApp-friendly text formatting."""

from __future__ import annotations

from contextual_hvac_rag.bot_whatsapp.formatter import format_for_whatsapp


def test_format_for_whatsapp_rewrites_markdown_tables_and_citations() -> None:
    source_text = """
    | AC Service Requirements and Steps (Follow in order, all steps are necessary):[5]() |
    | --- |
    | 1. Check voltage, current and earthing[5]() |
    | Change and/or clean primary filter | Every two months |

    | Additional Critical Safety Requirements:[6]() |
    | --- |
    | âœ“ Always disconnect power supply[6]() |
    | â€¢ Never attempt to repair it yourself[7]() |

    *Energy Efficiency Recommendations:*
    | Running AC at higher indoor temperature (24-27C range) consumes 15-25% less energy
    """

    formatted = format_for_whatsapp(source_text)

    assert "*AC Service Requirements and Steps (Follow in order, all steps are necessary):*" in formatted
    assert "1. Check voltage, current and earthing" in formatted
    assert "Change and/or clean primary filter - Every two months" in formatted
    assert "- Always disconnect power supply" in formatted
    assert "- Never attempt to repair it yourself" in formatted
    assert "*Energy Efficiency Recommendations:*" in formatted
    assert "[5]()" not in formatted
    assert "| --- |" not in formatted


def test_format_for_whatsapp_converts_task_table_rows_into_chat_bullets() -> None:
    source_text = """
    *Maintenance Task* - *Frequency/Description*
    Air Filter Cleaning - Every 2 weeks or as needed - Clean using vacuum cleaner or wash with lukewarm water and mild detergent
    Condenser Coil Wash - At least once a year to maximize efficiency and enhance AC working life
    """

    formatted = format_for_whatsapp(source_text)

    assert "*Maintenance Tasks*" in formatted
    assert "- Air Filter Cleaning" in formatted
    assert "  Every 2 weeks or as needed. Clean using vacuum cleaner or wash with lukewarm water and mild detergent." in formatted
    assert "- Condenser Coil Wash" in formatted
    assert "*Maintenance Task* - *Frequency/Description*" not in formatted
