"""Tests for evaluation CSV parsing helpers."""

from __future__ import annotations

from contextual_hvac_rag.eval.loader import parse_page_range


def test_parse_page_range_single_page() -> None:
    assert parse_page_range("[19]") == [19]


def test_parse_page_range_multiple_pages() -> None:
    assert parse_page_range("[29,30,31]") == [29, 30, 31]


def test_parse_page_range_invalid_input() -> None:
    assert parse_page_range("not-a-list") == []

