"""Metadata flattening tests."""

from __future__ import annotations

from contextual_hvac_rag.metadata.extractor import ExtractedMetadata
from contextual_hvac_rag.metadata.flatten import flatten_metadata_for_contextual


def test_flatten_metadata_for_contextual() -> None:
    metadata = ExtractedMetadata(
        doc_sha256="abc123",
        title="Demo Manual",
        document_type="service manual",
        version="RevA",
        date="Jan 2026",
        source="upload",
        toc_pages=(2, 3),
        index_pages=(99,),
        toc_preview="Contents preview",
        index_preview="Index preview",
    )

    flattened = flatten_metadata_for_contextual(metadata)

    assert flattened["doc_sha256"] == "abc123"
    assert flattened["type"] == "service manual"
    assert flattened["toc_pages"] == "2,3"
    assert flattened["index_pages"] == "99"

