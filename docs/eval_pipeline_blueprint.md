# Evaluation Pipeline Blueprint

This document describes the exact evaluation pipeline implemented in this repository so it can be recreated in another codebase with the same behavior.

## Goal

Run an offline evaluation over a golden CSV dataset against a Contextual agent, then compute document-level and page-level retrieval metrics.

The implementation is intentionally:

- live-query based (calls the real Contextual Agent Query API)
- retrieval-focused (not chunk-id based)
- tolerant of partial gold data
- file-output driven (JSONL per query + summary JSON)

## Current Implementation Location

Core code lives in:

- [run.py](/c:/Users/balaj/Documents/Contextual/Contextual-API/src/contextual_hvac_rag/eval/run.py)
- [loader.py](/c:/Users/balaj/Documents/Contextual/Contextual-API/src/contextual_hvac_rag/eval/loader.py)
- [metrics.py](/c:/Users/balaj/Documents/Contextual/Contextual-API/src/contextual_hvac_rag/eval/metrics.py)
- [normalize.py](/c:/Users/balaj/Documents/Contextual/Contextual-API/src/contextual_hvac_rag/eval/normalize.py)
- [latency.py](/c:/Users/balaj/Documents/Contextual/Contextual-API/src/contextual_hvac_rag/eval/latency.py)
- [writers.py](/c:/Users/balaj/Documents/Contextual/Contextual-API/src/contextual_hvac_rag/eval/writers.py)
- CLI wiring: [cli.py](/c:/Users/balaj/Documents/Contextual/Contextual-API/src/contextual_hvac_rag/cli.py)

## Golden Dataset Contract

The evaluator requires a CSV with this exact column order:

1. `Question`
2. `gold_sources`
3. `metadata`
4. `page_range`
5. `anchor_text`

Field meaning:

- `Question`: user query sent to the Contextual agent
- `gold_sources`: expected PDF filename
- `metadata`: difficulty label, typically `Easy`, `Medium`, or `Hard`
- `page_range`: string like `[19]` or `[29,30,31]`
- `anchor_text`: expected supporting snippet from the gold page(s)

## Env Dependencies

The evaluator uses the same Contextual env vars as the main app:

- `CONTEXTUAL_API_KEY`
- `CONTEXTUAL_AGENT_ID`
- optional `CONTEXTUAL_API_BASE` (default `https://api.contextual.ai/v1`)

This repo also uses:

- `EVAL_CONTEXTUAL_QUERY_MODE=query_acl`

That setting makes evaluation call the ACL endpoint directly for ACL-enabled agents and avoids the extra failed `/query` probe.

Supported values:

- `auto`
- `query`
- `query_acl`

Default in this repo: `query_acl`

## Query Behavior

Each row is treated as an independent query.

- no conversation reuse
- no WhatsApp-specific logic
- no caching
- non-streaming agent query

The current agent request shape is:

```json
{
  "messages": [
    {
      "role": "user",
      "content": "<Question>"
    }
  ]
}
```

For ACL-enabled agents, this repo uses:

```text
/v1/agents/{AGENT_ID}/query/acl
```

## Retrieval Normalization

The evaluator normalizes retrieval data from the Contextual payload on a best-effort basis.

It tries to extract:

- rank
- filename
- page
- snippet
- score

Important behavior:

- filename matching is robust:
  - Unicode normalized
  - basename extracted
  - trimmed
  - `casefold()`
- page is used if present
- if snippet text is present, it is used for anchor-text fallback matching
- if snippet is absent, page matching falls back to filename + explicit page only

## Missing Gold Field Policy

This is important and should be preserved exactly.

Rows with incomplete gold data are still queried and logged, but they are not always scored.

Document-level scoring:

- if `gold_sources` is blank:
  - the row is not included in DOC metrics
  - per-query fields are emitted as:
    - `doc_scored: false`
    - doc metric fields are `null`

Page-level scoring:

- if `gold_sources` is blank, or both `page_range` and `anchor_text` are blank:
  - the row is not included in PAGE metrics
  - per-query fields are emitted as:
    - `page_scored: false`
    - page metric fields are `null`

The row is still:

- queried
- logged
- included in latency summaries

## Metrics

Metrics are computed for:

- `k in {1, 3, 5, 10}`

### DOC Metrics

Computed:

- `Recall@k`
- `MRR@10`
- `nDCG@k`

DOC relevance is binary:

- `1` if normalized retrieved filename matches `gold_sources`
- `0` otherwise

### PAGE Metrics

Computed:

- `Recall@k`
- `MRR@10`
- `nDCG@k`

PAGE matching logic:

1. First try exact page hit:
   - same normalized filename
   - retrieved page is in parsed `page_range`
2. If exact page cannot be proven, fall back to anchor-text fuzzy matching:
   - compare `anchor_text` vs retrieved snippet
   - configurable threshold, default `80`

PAGE graded relevance:

- `2` if exact page hit or anchor-text fallback hit
- `1` if correct document but wrong or unknown page
- `0` otherwise

That means page `nDCG` intentionally gives partial credit for correct-document/wrong-page retrievals.

This is why page `nDCG` can be high even when page `Recall@k` is low.

## Latency

Every query records:

- total end-to-end latency in milliseconds

Best-effort stage timings are also extracted when available:

- `embed`
- `search`
- `rerank`
- `generate`

If the API does not expose a stage in `workflow_trace`, that field remains `null`.

## Outputs

### 1. Per-query JSONL

One JSON object per input row.

Current output fields:

- `question_id`
- `Question`
- `difficulty`
- `gold_sources`
- `gold_pages`
- `anchor_text`
- `answer_text`
- `normalized_retrieval_topN`
- `doc_scored`
- `page_scored`
- `doc_rr`
- `page_rr`
- `doc_hit@1`, `doc_hit@3`, `doc_hit@5`, `doc_hit@10`
- `page_hit@1`, `page_hit@3`, `page_hit@5`, `page_hit@10`
- `doc_ndcg@1`, `doc_ndcg@3`, `doc_ndcg@5`, `doc_ndcg@10`
- `page_ndcg@1`, `page_ndcg@3`, `page_ndcg@5`, `page_ndcg@10`
- `latency_ms`
- `error_type`
- `error_message`
- `contextual_conversation_id` if returned
- `contextual_message_id` if returned

### 2. Summary JSON

Current top-level fields:

- `retrieval`
- `metric_notes`
- `by_difficulty`
- `by_gold_sources`
- `by_gold_source`
- `latency_ms`
- `index_stats`

Notes:

- `by_gold_source` is kept as a compatibility alias for `by_gold_sources`
- `index_stats` is currently:
  - `documents: "not_available"`
  - `chunks: "not_available"`
  - `vector_dim: "not_available"`

### 3. Console Summary

The CLI prints:

- number of evaluated rows
- DOC vs PAGE metric table
- note explaining page nDCG graded relevance
- output file paths

## CLI

Current command:

```bash
contextual-hvac-rag eval --input ./eval/golden.csv --out ./eval/results --top-k 10
```

Supported flags:

- `--input`
- `--out`
- `--top-k`
- `--anchor-threshold`
- `--limit`

`--limit` is used for smoke testing, for example:

```bash
contextual-hvac-rag eval --input ./eval/golden.csv --out ./eval/results_smoke --top-k 10 --limit 5
```

## Important Known Behaviors

- If retrieval snippets are missing, anchor-text fallback cannot help for that row.
- For ACL-enabled agents, direct `query/acl` significantly reduces evaluation runtime.
- The evaluator is correctness-oriented; it does not cache or reuse prior responses.
- It uses the real agent response as-is and does not clean answer formatting.

## Reimplementation Checklist

To recreate this in another project, preserve all of the following:

- exact CSV header contract
- robust page-range parsing
- stable `question_id` generation
- filename normalization for DOC matching
- anchor-text fuzzy fallback for PAGE matching
- graded PAGE relevance (`2/1/0`)
- skip scoring for incomplete gold rows
- per-query JSONL + summary JSON output split
- latency extraction from `workflow_trace`
- direct ACL query mode support
- `--limit` smoke-test mode

## Recommended Validation

After reimplementation:

1. Run parser unit tests:
   - page-range parsing
   - metrics
   - normalization
2. Run a 5-row smoke test against a real CSV
3. Confirm:
   - JSONL record keys match
   - summary includes `metric_notes`
   - no extra `/query` 400s appear if ACL mode is direct
4. Then run the full CSV
