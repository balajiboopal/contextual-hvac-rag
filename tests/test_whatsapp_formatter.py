"""Tests for WhatsApp-friendly text formatting."""

from __future__ import annotations

from contextual_hvac_rag.bot_whatsapp.formatter import format_for_whatsapp, format_reply_chunks


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
    assert "- Change and/or clean primary filter" in formatted
    assert "  Every two months." in formatted
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


def test_format_for_whatsapp_rewrites_two_column_pipe_rows_as_bullets() -> None:
    source_text = """
    | **Initial Safety Checks** | **Required Actions** |
    |--------------------------|---------------------|
    | Power and Electrical | • Check the breaker • Verify power supply |
    | Remote Control | • Replace batteries if needed |
    """

    formatted = format_for_whatsapp(source_text)

    assert "*Initial Safety Checks*" in formatted
    assert "- Power and Electrical" in formatted
    assert "  - Check the breaker." in formatted
    assert "  - Verify power supply." in formatted
    assert "- Remote Control" in formatted
    assert "  Replace batteries if needed." in formatted


def test_format_reply_chunks_splits_long_messages() -> None:
    source_text = "\n\n".join(
        [
            "Section one. " * 20,
            "Section two. " * 20,
            "Section three. " * 20,
        ]
    )

    chunks = format_reply_chunks(source_text, max_chars=180)

    assert len(chunks) >= 2
    assert all(len(chunk) <= 180 for chunk in chunks)


def test_format_for_whatsapp_strips_broken_numeric_citation_tokens() -> None:
    source_text = "¹()²()³() Regular maintenance is required. 1()2()3() Always inspect the unit."

    formatted = format_for_whatsapp(source_text)

    assert formatted == "Regular maintenance is required. Always inspect the unit."
