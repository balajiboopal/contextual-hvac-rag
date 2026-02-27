"""Flatten extracted metadata into Contextual custom metadata fields."""

from __future__ import annotations

from contextual_hvac_rag.metadata.extractor import ExtractedMetadata


def flatten_metadata_for_contextual(metadata: ExtractedMetadata) -> dict[str, str]:
    """Return a JSON-serializable flat dictionary for Contextual custom metadata."""

    return {
        "doc_sha256": metadata.doc_sha256,
        "title": metadata.title,
        "type": metadata.document_type,
        "version": metadata.version,
        "date": metadata.date,
        "source": metadata.source,
        "toc_pages": ",".join(str(page) for page in metadata.toc_pages),
        "index_pages": ",".join(str(page) for page in metadata.index_pages),
        "toc_preview": metadata.toc_preview,
        "index_preview": metadata.index_preview,
    }
