"""Tests for retrieval metrics."""

from __future__ import annotations

from contextual_hvac_rag.eval.metrics import mrr_at_k, ndcg_at_k, recall_at_k


def test_recall_at_k_hits_when_relevant_item_present() -> None:
    assert recall_at_k([0, 1, 0], 3) == 1.0
    assert recall_at_k([0, 0, 0], 3) == 0.0


def test_mrr_at_k_uses_first_relevant_rank() -> None:
    assert mrr_at_k([0, 0, 1, 1], 4) == 1.0 / 3.0
    assert mrr_at_k([0, 0, 0], 3) == 0.0


def test_ndcg_at_k_handles_graded_relevance() -> None:
    perfect = ndcg_at_k([2, 1, 0], 3)
    imperfect = ndcg_at_k([0, 2, 1], 3)

    assert perfect == 1.0
    assert 0.0 < imperfect < 1.0
