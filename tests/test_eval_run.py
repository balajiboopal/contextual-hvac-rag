"""Tests for evaluation runner aggregation and scoring eligibility."""

from __future__ import annotations

from contextual_hvac_rag.eval.loader import GoldenDatasetRow
from contextual_hvac_rag.eval.run import _aggregate_metrics, _is_doc_scorable, _is_page_scorable


def test_scoring_eligibility_uses_available_gold_fields() -> None:
    doc_only = GoldenDatasetRow(
        row_index=0,
        question_id="q1",
        question="What is the answer?",
        gold_source="manual.pdf",
        difficulty="Easy",
        gold_pages=[],
        anchor_text="",
    )
    with_page_anchor = GoldenDatasetRow(
        row_index=1,
        question_id="q2",
        question="Another question",
        gold_source="manual.pdf",
        difficulty="Easy",
        gold_pages=[3],
        anchor_text="snippet",
    )
    missing_doc = GoldenDatasetRow(
        row_index=2,
        question_id="q3",
        question="Third question",
        gold_source="",
        difficulty="Easy",
        gold_pages=[3],
        anchor_text="snippet",
    )

    assert _is_doc_scorable(doc_only) is True
    assert _is_page_scorable(doc_only) is False
    assert _is_doc_scorable(with_page_anchor) is True
    assert _is_page_scorable(with_page_anchor) is True
    assert _is_doc_scorable(missing_doc) is False
    assert _is_page_scorable(missing_doc) is False


def test_aggregate_metrics_ignores_unrated_rows() -> None:
    records = [
        {
            "doc_scored": True,
            "page_scored": True,
            "doc_hit@1": True,
            "page_hit@1": False,
            "doc_ndcg@1": 1.0,
            "page_ndcg@1": 0.0,
            "doc_hit@3": True,
            "page_hit@3": True,
            "doc_ndcg@3": 1.0,
            "page_ndcg@3": 0.5,
            "doc_hit@5": True,
            "page_hit@5": True,
            "doc_ndcg@5": 1.0,
            "page_ndcg@5": 0.5,
            "doc_hit@10": True,
            "page_hit@10": True,
            "doc_ndcg@10": 1.0,
            "page_ndcg@10": 0.5,
            "doc_rr": 1.0,
            "page_rr": 0.5,
        },
        {
            "doc_scored": False,
            "page_scored": False,
            "doc_hit@1": None,
            "page_hit@1": None,
            "doc_ndcg@1": None,
            "page_ndcg@1": None,
            "doc_hit@3": None,
            "page_hit@3": None,
            "doc_ndcg@3": None,
            "page_ndcg@3": None,
            "doc_hit@5": None,
            "page_hit@5": None,
            "doc_ndcg@5": None,
            "page_ndcg@5": None,
            "doc_hit@10": None,
            "page_hit@10": None,
            "doc_ndcg@10": None,
            "page_ndcg@10": None,
            "doc_rr": None,
            "page_rr": None,
        },
    ]

    summary = _aggregate_metrics(records, ks=(1, 3, 5, 10))

    assert summary["doc"]["recall@1"] == 1.0
    assert summary["page"]["recall@1"] == 0.0
    assert summary["doc"]["mrr@10"] == 1.0
    assert summary["page"]["mrr@10"] == 0.5
    assert summary["doc"]["scored_rows"] == 1.0
    assert summary["page"]["scored_rows"] == 1.0
