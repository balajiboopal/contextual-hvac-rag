"""Flatten extracted metadata into Contextual custom metadata fields."""

from __future__ import annotations

from contextual_hvac_rag.metadata.extractor import ExtractedMetadata


def flatten_metadata_for_contextual(metadata: ExtractedMetadata) -> dict[str, str]:
    """Return a JSON-serializable flat dictionary for Contextual custom metadata."""

    toc_pages = ",".join(str(hit.page) for hit in metadata.toc)
    index_pages = ",".join(str(hit.page) for hit in metadata.index)
    toc_preview = metadata.toc[0].text[:250] if metadata.toc else ""
    index_preview = metadata.index[0].text[:250] if metadata.index else ""

    return {
        "doc_sha256": metadata.doc_sha256,
        "title": metadata.title or "",
        "type": metadata.document_type or "",
        "version": metadata.version or "",
        "date": metadata.date or "",
        "source": metadata.source,
        "toc_pages": toc_pages,
        "index_pages": index_pages,
        "toc_preview": toc_preview,
        "index_preview": index_preview,
    }
