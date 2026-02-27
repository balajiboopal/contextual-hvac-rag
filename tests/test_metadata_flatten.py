"""Metadata flattening tests."""

from __future__ import annotations

from contextual_hvac_rag.metadata.extractor import ExtractedMetadata, PageHit
from contextual_hvac_rag.metadata.flatten import flatten_metadata_for_contextual


def test_flatten_metadata_for_contextual() -> None:
    metadata = ExtractedMetadata(
        doc_sha256="abc123",
        title="Demo Manual",
        document_type="service manual",
        version="RevA",
        date="Jan 2026",
        source="upload",
        toc=(
            PageHit(page=2, score=16, text="Contents preview"),
            PageHit(page=3, score=14, text="More contents preview"),
        ),
        index=(PageHit(page=99, score=18, text="Index preview"),),
    )

    flattened = flatten_metadata_for_contextual(metadata)

    assert flattened["doc_sha256"] == "abc123"
    assert flattened["type"] == "service manual"
    assert flattened["toc_pages"] == "2,3"
    assert flattened["index_pages"] == "99"
    assert flattened["toc_preview"] == "Contents preview"

