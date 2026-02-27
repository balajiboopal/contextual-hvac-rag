"""Tests for metadata heuristics that do not require real PDFs."""

from __future__ import annotations

from contextual_hvac_rag.metadata.extractor import index_score, looks_like_contact_or_imprint, toc_score


def test_toc_score_handles_spaced_dot_leaders() -> None:
    page_text = "\n".join(
        [
            "Content",
            "1 Overview . . . . . . 1",
            "2 Installation . . . . . . 4",
            "3 Maintenance . . . . . . 8",
            "4 Troubleshooting . . . . . . 12",
            "Appendix A . . . . . . 15",
            "Appendix B . . . . . . 16",
            "Notes . . . . . . 17",
        ]
    )

    assert toc_score(page_text) >= 10


def test_contact_heavy_page_is_excluded() -> None:
    page_text = """
    Contact us
    support@example.com
    sales@example.com
    www.example.com
    https://example.com
    T +1 555 123 4567
    F +1 555 987 6543
    """

    assert looks_like_contact_or_imprint(page_text.lower()) is True
    assert toc_score(page_text) == 0
    assert index_score(page_text) == 0


def test_index_score_prefers_back_page_style_lines() -> None:
    page_text = "\n".join(
        [
            "Index",
            "air filter 7",
            "blower assembly 11",
            "compressor 18",
            "condenser fan 23",
            "defrost cycle 29",
            "expansion valve 34",
            "heat exchanger 41",
            "thermostat 48",
            "wiring harness 52",
        ]
    )

    assert index_score(page_text) >= 12
