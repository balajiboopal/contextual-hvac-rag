"""Tests for retrieval normalization helpers."""

from __future__ import annotations

from contextual_hvac_rag.eval.normalize import normalize_retrieval_items


def test_normalize_retrieval_items_reads_nested_metadata_fields() -> None:
    payload = {
        "retrieval_contents": [
            {
                "metadata": {
                    "source": {
                        "filename": "Manual_A.pdf",
                        "page_number": "19",
                    },
                    "snippet": "Expected anchor text",
                },
                "rerank_score": 0.87,
            }
        ]
    }

    items = normalize_retrieval_items(payload=payload, top_n=10)

    assert len(items) == 1
    assert items[0].filename == "Manual_A.pdf"
    assert items[0].page == 19
    assert items[0].snippet == "Expected anchor text"
    assert items[0].score == 0.87
