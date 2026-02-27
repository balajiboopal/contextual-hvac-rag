# Evaluation Placeholder

This directory reserves the structure for the future golden-dataset and retrieval evaluation pipeline.

## Planned JSONL Schema

Each JSONL row should represent one evaluation case with fields similar to:

- `question`: string
- `gold_sources`: list of expected source references such as document ids, chunk ids, or page ids
- `metadata`: object containing labels like `difficulty`, `type` (`synthetic` or `handwritten`), and traceability fields

## Planned Metrics

- `Recall@K`
- `MRR`
- `citation_validity`
- `source_hit_rate`

## Notes

- Keep fake placeholders only in committed examples.
- Store any real evaluation data outside version control unless it is explicitly sanitized for sharing.

