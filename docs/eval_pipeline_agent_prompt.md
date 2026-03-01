# Prompt: Rebuild This Evaluation Pipeline In Another Repo

Use this prompt with another coding agent when you want the open-source version of this project to implement the same evaluation pipeline behavior as this repository.

## Copy-Paste Prompt

```md
Implement an evaluation pipeline that exactly matches the behavior of the existing `contextual-hvac-rag` repository's eval system.

This must be an additive change only. Do not rewrite unrelated ingestion or bot code.

Goal:
- run an offline evaluation over a golden CSV against the Contextual Agent Query API
- compute DOC-level and PAGE-level retrieval metrics
- emit per-query JSONL + summary JSON + console summary

Golden CSV contract (must be exact, same order):
1. Question
2. gold_sources
3. metadata
4. page_range
5. anchor_text

Env vars:
- CONTEXTUAL_API_KEY
- CONTEXTUAL_AGENT_ID
- optional CONTEXTUAL_API_BASE (default https://api.contextual.ai/v1)
- EVAL_CONTEXTUAL_QUERY_MODE with supported values: auto, query, query_acl
- default EVAL_CONTEXTUAL_QUERY_MODE must be query_acl

Query behavior:
- each row is an independent query
- no conversation reuse
- no caching
- non-streaming call
- request body shape:
  {
    "messages": [
      {"role": "user", "content": "<Question>"}
    ]
  }
- if using ACL mode directly, call /v1/agents/{AGENT_ID}/query/acl

Modules to create:
- eval/run.py
- eval/loader.py
- eval/metrics.py
- eval/normalize.py
- eval/latency.py
- eval/writers.py
- wire into the existing top-level CLI as:
  contextual-hvac-rag eval --input <csv> --out <dir> --top-k 10

Required behavior:

1. CSV loading
- validate exact headers
- parse page_range safely from strings like "[19]" or "[29,30,31]"
- stable question_id per row using row index + question text hash

2. Retrieval normalization
- best-effort normalize top N retrievals into:
  - rank
  - filename
  - page
  - snippet
  - score
- filename comparison must be robust:
  - Unicode normalize
  - basename only
  - trim
  - casefold

3. Missing gold policy (must match exactly)
- rows with missing gold fields are still queried and logged
- but scoring must be skipped when gold is insufficient

DOC scoring:
- if gold_sources is blank:
  - doc_scored = false
  - doc metric fields = null
  - row is excluded from aggregated DOC metrics

PAGE scoring:
- if gold_sources is blank, or both page_range and anchor_text are blank:
  - page_scored = false
  - page metric fields = null
  - row is excluded from aggregated PAGE metrics

4. Metrics
Compute for k in {1,3,5,10}:

DOC:
- Recall@k
- MRR@10
- nDCG@k

DOC relevance:
- 1 if retrieved filename matches gold_sources
- 0 otherwise

PAGE:
- Recall@k
- MRR@10
- nDCG@k

PAGE hit logic:
- exact page hit if same normalized filename and retrieved page is in page_range
- otherwise fallback to anchor_text fuzzy match against retrieved snippet
- anchor threshold configurable, default 80

PAGE graded relevance:
- rel=2 if exact page hit or anchor-text fallback hit
- rel=1 if correct document but wrong or unknown page
- rel=0 otherwise

Important:
- page nDCG intentionally gives partial credit for correct-doc/wrong-page retrievals
- this must be preserved

5. Latency
- always record total elapsed ms
- extract optional stage timings from workflow_trace if available:
  - embed
  - search
  - rerank
  - generate
- if not available, store null

6. Outputs

Per-query JSONL fields:
- question_id
- Question
- difficulty
- gold_sources
- gold_pages
- anchor_text
- answer_text
- normalized_retrieval_topN
- doc_scored
- page_scored
- doc_rr
- page_rr
- doc_hit@1, doc_hit@3, doc_hit@5, doc_hit@10
- page_hit@1, page_hit@3, page_hit@5, page_hit@10
- doc_ndcg@1, doc_ndcg@3, doc_ndcg@5, doc_ndcg@10
- page_ndcg@1, page_ndcg@3, page_ndcg@5, page_ndcg@10
- latency_ms
- error_type
- error_message
- contextual_conversation_id if returned
- contextual_message_id if returned

Summary JSON top-level fields:
- retrieval
- metric_notes
- by_difficulty
- by_gold_sources
- by_gold_source (compat alias)
- latency_ms
- index_stats

metric_notes must include:
- page_ndcg explanation that rel=2 means exact page/anchor hit, rel=1 means correct doc but wrong/unknown page

index_stats can be:
- documents: "not_available"
- chunks: "not_available"
- vector_dim: "not_available"

7. CLI behavior
- support:
  - --input
  - --out
  - --top-k
  - --anchor-threshold
  - --limit
- --limit is for smoke testing subsets, e.g. 5 rows

8. Tests
Add minimal tests for:
- page_range parsing
- recall/mrr/ndcg
- unrated-row exclusion from aggregation
- summary includes page_ndcg metric note

9. Docs
Create a markdown file documenting:
- exact CSV contract
- missing gold policy
- metric definitions
- page nDCG partial-credit semantics
- direct ACL eval mode
- exact run command

Implementation constraints:
- Python 3.11+
- type hints
- concise docstrings
- additive only
- do not invent chunk-id metrics
- do not require gold chunk ids

After implementing, run:
- tests
- a small smoke test (limit 5)

Then report:
- files added/changed
- exact run command for full CSV
- any caveats about missing snippets affecting anchor-text fallback
```

## Usage Note

If you want that other agent to stay aligned with this repo’s current behavior, also paste:

- [AGENT_CONTEXT.md](/c:/Users/balaj/Documents/Contextual/Contextual-API/docs/agent/AGENT_CONTEXT.md)
- [eval_pipeline_blueprint.md](/c:/Users/balaj/Documents/Contextual/Contextual-API/docs/eval_pipeline_blueprint.md)

at the top of the prompt.
