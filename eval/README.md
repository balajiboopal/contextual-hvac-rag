# Evaluation Pipeline

This repository now includes an offline evaluation pipeline for a golden-dataset CSV.

## Golden CSV Format

The evaluator requires a CSV with the exact columns below, in this exact order:

- `Question`
- `gold_sources`
- `metadata`
- `page_range`
- `anchor_text`

Column meanings:

- `Question`: the user query sent to the Contextual agent
- `gold_sources`: the expected PDF filename
- `metadata`: the difficulty label (`Easy`, `Medium`, or `Hard`)
- `page_range`: a string like `[19]` or `[29,30,31]`
- `anchor_text`: the expected snippet from the relevant page(s)

## How To Run

```bash
contextual-hvac-rag eval --input ./eval/golden.csv --out ./eval/results --top-k 10
```

Optional tuning:

```bash
contextual-hvac-rag eval \
  --input ./eval/golden.csv \
  --out ./eval/results \
  --top-k 10 \
  --anchor-threshold 80
```

The evaluator uses direct `query/acl` mode by default for faster runs with ACL-enabled agents. Override it with:

```env
EVAL_CONTEXTUAL_QUERY_MODE=auto
```

Run only a quick subset during smoke testing:

```bash
contextual-hvac-rag eval \
  --input ./eval/golden.csv \
  --out ./eval/results_smoke \
  --top-k 10 \
  --limit 5
```

## What It Produces

The command writes:

- `per_query_results.jsonl`
  - one JSON object per question
  - includes answer text, normalized retrieval items, hit flags, MRR, nDCG, latency, and explicit `error_type` / `error_message` fields on failures
- `summary.json`
  - overall metrics
  - breakdown by difficulty
  - breakdown by `gold_sources` (under `by_gold_sources`)
  - latency summaries
  - best-effort index stats (currently `not_available`)

The CLI also prints a readable console summary table.

## Metrics

For `k in {1, 3, 5, 10}`, the evaluator computes:

- DOC metrics:
  - `Recall@k`
  - `MRR@10`
  - `nDCG@k`
- PAGE metrics:
  - `Recall@k`
  - `MRR@10`
  - `nDCG@k`

### DOC Matching

- A hit is counted when the retrieved filename matches `gold_sources`
- Filename matching is normalized using Unicode normalization, `Path.name`, trimming, and `casefold()`
- If `gold_sources` is blank for a row, that row is not included in DOC-level scoring

### PAGE Matching

- Preferred: exact page hit using `gold_sources + page_range`
- Fallback: if page is missing or unusable, `anchor_text` fuzzy matching is used against the retrieved snippet
- Default fuzzy threshold: `80`
- If both `page_range` and `anchor_text` are blank for a row, that row is not included in PAGE-level scoring

Page-wise graded relevance:

- `2` for exact page hit (or anchor-text fallback hit)
- `1` for correct document but wrong or unknown page
- `0` otherwise

Because of that grading, page `nDCG` can still be high even when page `Recall@k` is low. A correct document retrieved on the wrong page still earns partial page relevance (`rel=1`).

## Latency

Each query always records:

- total end-to-end latency in milliseconds

The evaluator also tries to infer these stage timings from the API payload when available:

- `embed`
- `search`
- `rerank`
- `generate`

If the payload does not expose a stage, that value remains `null`.

## Limitations

- No gold chunk ids are used or invented
- Chunk-wise metrics are intentionally not computed
- Stage timings depend on what the Contextual API exposes in `workflow_trace`
- Index stats are currently reported as:
  - `documents: "not_available"`
  - `chunks: "not_available"`
  - `vector_dim: "not_available"`
- Retrieval normalization is best-effort because payload shapes can vary

## Example Summary

```json
{
  "retrieval": {
    "doc": {
      "recall@1": 0.62,
      "recall@3": 0.78,
      "recall@5": 0.84,
      "recall@10": 0.91,
      "mrr@10": 0.73,
      "ndcg@10": 0.8
    },
    "page": {
      "recall@1": 0.45,
      "recall@3": 0.63,
      "recall@5": 0.7,
      "recall@10": 0.79,
      "mrr@10": 0.58,
      "ndcg@10": 0.67
    }
  },
  "latency_ms": {
    "total": {
      "mean": 1850,
      "p50": 1620,
      "p95": 4200
    }
  },
  "index_stats": {
    "documents": "not_available",
    "chunks": "not_available",
    "vector_dim": "not_available"
  }
}
```
