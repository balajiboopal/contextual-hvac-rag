"""Evaluation runner for golden-dataset CSV files."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import typer

from contextual_hvac_rag.config import get_settings
from contextual_hvac_rag.contextual_client import ContextualClient, ContextualClientError
from contextual_hvac_rag.eval.latency import extract_latency_ms, summarize_latencies
from contextual_hvac_rag.eval.loader import GoldenDatasetRow, load_golden_dataset
from contextual_hvac_rag.eval.metrics import average, mrr_at_k, ndcg_at_k, recall_at_k
from contextual_hvac_rag.eval.normalize import (
    NormalizedRetrievalItem,
    anchor_text_matches,
    normalize_filename,
    normalize_retrieval_items,
)
from contextual_hvac_rag.eval.writers import append_jsonl, write_json

LOGGER = logging.getLogger(__name__)
DEFAULT_EVAL_KS = (1, 3, 5, 10)


@dataclass(frozen=True, slots=True)
class QueryEvaluationArtifact:
    """Computed metrics for a single golden-dataset row."""

    record: dict[str, Any]
    difficulty: str
    gold_source: str
    latencies: dict[str, float | None]


def run_evaluation(
    *,
    input_csv: Path,
    out_dir: Path,
    top_k: int = 10,
    anchor_threshold: int = 80,
) -> dict[str, Any]:
    """Run the offline evaluation pipeline and return the aggregated summary."""

    if top_k < 10:
        raise ValueError("--top-k must be at least 10 because metrics are reported through @10.")

    settings = get_settings()
    missing = settings.missing_contextual_agent_vars()
    if missing:
        raise ContextualClientError(
            f"Missing required Contextual settings: {', '.join(missing)}"
        )

    rows = load_golden_dataset(input_csv)
    out_dir.mkdir(parents=True, exist_ok=True)
    per_query_path = out_dir / "per_query_results.jsonl"
    summary_path = out_dir / "summary.json"
    if per_query_path.exists():
        per_query_path.unlink()

    artifacts: list[QueryEvaluationArtifact] = []
    with ContextualClient(settings) as client:
        for row in rows:
            artifact = _evaluate_single_row(
                client=client,
                row=row,
                top_k=top_k,
                anchor_threshold=anchor_threshold,
            )
            append_jsonl(per_query_path, artifact.record)
            artifacts.append(artifact)

    summary = build_summary(artifacts)
    write_json(summary_path, summary)
    _print_console_summary(summary=summary, total_queries=len(rows), out_dir=out_dir)
    return summary


def _evaluate_single_row(
    *,
    client: ContextualClient,
    row: GoldenDatasetRow,
    top_k: int,
    anchor_threshold: int,
) -> QueryEvaluationArtifact:
    ks = [k for k in DEFAULT_EVAL_KS if k <= top_k]
    if 10 not in ks:
        ks.append(10)
        ks = sorted(set(ks))

    started_at = time.perf_counter()
    error_message: str | None = None
    error_type: str | None = None
    answer_text = ""
    retrieval_items: list[NormalizedRetrievalItem] = []
    latencies: dict[str, float | None]
    response_payload: dict[str, Any] = {}

    try:
        result = client.query_agent(message=row.question, conversation_id=None)
        elapsed_ms = (time.perf_counter() - started_at) * 1000.0
        answer_text = result.answer_text
        response_payload = result.payload
        retrieval_items = normalize_retrieval_items(payload=result.payload, top_n=top_k)
        latencies = extract_latency_ms(payload=result.payload, total_elapsed_ms=elapsed_ms)
    except Exception as exc:  # noqa: BLE001
        elapsed_ms = (time.perf_counter() - started_at) * 1000.0
        latencies = extract_latency_ms(payload={}, total_elapsed_ms=elapsed_ms)
        error_message = str(exc)
        error_type = type(exc).__name__
        LOGGER.exception("Evaluation query failed for row %s", row.row_index)

    doc_relevances, page_grades, page_binary = _compute_relevance_lists(
        row=row,
        retrieval_items=retrieval_items,
        anchor_threshold=anchor_threshold,
    )

    record: dict[str, Any] = {
        "question_id": row.question_id,
        "Question": row.question,
        "difficulty": row.difficulty,
        "gold_sources": row.gold_source,
        "gold_pages": row.gold_pages,
        "anchor_text": row.anchor_text,
        "answer_text": answer_text,
        "normalized_retrieval_topN": [item.to_dict() for item in retrieval_items],
        "doc_rr": mrr_at_k(doc_relevances, 10),
        "page_rr": mrr_at_k(page_binary, 10),
        "latency_ms": {
            "total": latencies["total"],
            "embed": latencies["embed"],
            "search": latencies["search"],
            "rerank": latencies["rerank"],
            "generate": latencies["generate"],
        },
        "error_type": error_type,
        "error_message": error_message,
    }

    for k in ks:
        record[f"doc_hit@{k}"] = bool(recall_at_k(doc_relevances, k))
        record[f"page_hit@{k}"] = bool(recall_at_k(page_binary, k))
        record[f"doc_ndcg@{k}"] = ndcg_at_k(doc_relevances, k)
        record[f"page_ndcg@{k}"] = ndcg_at_k(page_grades, k)

    if 10 not in ks:
        record["doc_hit@10"] = bool(recall_at_k(doc_relevances, 10))
        record["page_hit@10"] = bool(recall_at_k(page_binary, 10))
        record["doc_ndcg@10"] = ndcg_at_k(doc_relevances, 10)
        record["page_ndcg@10"] = ndcg_at_k(page_grades, 10)

    if response_payload:
        record["contextual_conversation_id"] = response_payload.get("conversation_id")
        record["contextual_message_id"] = response_payload.get("message_id")

    return QueryEvaluationArtifact(
        record=record,
        difficulty=row.difficulty or "Unknown",
        gold_source=row.gold_source,
        latencies=latencies,
    )


def build_summary(artifacts: list[QueryEvaluationArtifact]) -> dict[str, Any]:
    """Build the aggregated evaluation summary JSON."""

    ks = DEFAULT_EVAL_KS
    overall = _aggregate_metrics([artifact.record for artifact in artifacts], ks=ks)

    by_difficulty: dict[str, Any] = {}
    difficulty_groups = sorted({artifact.difficulty or "Unknown" for artifact in artifacts})
    for difficulty in difficulty_groups:
        records = [artifact.record for artifact in artifacts if artifact.difficulty == difficulty]
        by_difficulty[difficulty] = _aggregate_metrics(records, ks=ks)

    by_source: dict[str, Any] = {}
    source_groups = sorted({artifact.gold_source for artifact in artifacts})
    for source in source_groups:
        records = [artifact.record for artifact in artifacts if artifact.gold_source == source]
        by_source[source] = _aggregate_metrics(records, ks=ks)

    latency_summary = summarize_latencies([artifact.latencies for artifact in artifacts])
    return {
        "retrieval": overall,
        "by_difficulty": by_difficulty,
        "by_gold_sources": by_source,
        "by_gold_source": by_source,
        "latency_ms": latency_summary,
        "index_stats": {
            "documents": "not_available",
            "chunks": "not_available",
            "vector_dim": "not_available",
        },
    }


def run_evaluation_cli(
    input_csv: Path = typer.Option(..., "--input", exists=True, dir_okay=False),
    out_dir: Path = typer.Option(..., "--out", file_okay=False),
    top_k: int = typer.Option(10, "--top-k", min=10),
    anchor_threshold: int = typer.Option(80, "--anchor-threshold", min=0, max=100),
) -> None:
    """CLI entry point for the offline evaluation pipeline."""

    run_evaluation(
        input_csv=input_csv,
        out_dir=out_dir,
        top_k=top_k,
        anchor_threshold=anchor_threshold,
    )


def _compute_relevance_lists(
    *,
    row: GoldenDatasetRow,
    retrieval_items: list[NormalizedRetrievalItem],
    anchor_threshold: int,
) -> tuple[list[int], list[int], list[int]]:
    gold_filename = normalize_filename(row.gold_source)
    doc_relevances: list[int] = []
    page_grades: list[int] = []
    page_binary: list[int] = []

    for item in retrieval_items:
        same_doc = bool(gold_filename) and item.normalized_filename == gold_filename
        doc_relevances.append(1 if same_doc else 0)

        if not same_doc:
            page_grades.append(0)
            page_binary.append(0)
            continue

        exact_page_hit = item.page is not None and item.page in row.gold_pages
        snippet_hit = anchor_text_matches(
            anchor_text=row.anchor_text,
            snippet=item.snippet,
            threshold=anchor_threshold,
        )
        if exact_page_hit or snippet_hit:
            page_grades.append(2)
            page_binary.append(1)
        else:
            page_grades.append(1)
            page_binary.append(0)
    return doc_relevances, page_grades, page_binary


def _aggregate_metrics(records: list[dict[str, Any]], *, ks: tuple[int, ...]) -> dict[str, Any]:
    doc_metrics: dict[str, float] = {}
    page_metrics: dict[str, float] = {}

    for k in ks:
        doc_metrics[f"recall@{k}"] = average([float(record.get(f"doc_hit@{k}", 0.0)) for record in records])
        page_metrics[f"recall@{k}"] = average([float(record.get(f"page_hit@{k}", 0.0)) for record in records])
        doc_metrics[f"ndcg@{k}"] = average([float(record.get(f"doc_ndcg@{k}", 0.0)) for record in records])
        page_metrics[f"ndcg@{k}"] = average([float(record.get(f"page_ndcg@{k}", 0.0)) for record in records])

    doc_metrics["mrr@10"] = average([float(record.get("doc_rr", 0.0)) for record in records])
    page_metrics["mrr@10"] = average([float(record.get("page_rr", 0.0)) for record in records])
    return {"doc": doc_metrics, "page": page_metrics}


def _print_console_summary(*, summary: dict[str, Any], total_queries: int, out_dir: Path) -> None:
    by_source = summary.get("by_gold_sources", {})
    typer.echo(f"Evaluated {total_queries} questions")
    typer.echo("")
    typer.echo("Metric               DOC       PAGE")
    typer.echo("-----------------------------------")
    retrieval = summary["retrieval"]
    for metric_key in ("recall@1", "recall@3", "recall@5", "recall@10", "mrr@10", "ndcg@10"):
        doc_value = retrieval["doc"].get(metric_key, 0.0)
        page_value = retrieval["page"].get(metric_key, 0.0)
        typer.echo(f"{metric_key:<18} {doc_value:>5.3f}     {page_value:>5.3f}")
    typer.echo("")
    typer.echo(f"Per-PDF breakdowns: {len(by_source)}")
    typer.echo(f"Per-query JSONL: {out_dir / 'per_query_results.jsonl'}")
    typer.echo(f"Summary JSON:    {out_dir / 'summary.json'}")
