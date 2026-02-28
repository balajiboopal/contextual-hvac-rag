"""Best-effort normalization of retrieval results and matching helpers."""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class NormalizedRetrievalItem:
    """A retrieval item normalized across varying API payload shapes."""

    rank: int
    filename: str
    normalized_filename: str
    page: int | None
    snippet: str | None
    score: float | None

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable representation."""

        return {
            "rank": self.rank,
            "filename": self.filename,
            "page": self.page,
            "snippet": self.snippet,
            "score": self.score,
        }


def normalize_retrieval_items(*, payload: dict[str, Any], top_n: int) -> list[NormalizedRetrievalItem]:
    """Normalize retrieval entries from the Contextual agent payload."""

    items: list[NormalizedRetrievalItem] = []
    raw_retrievals = payload.get("retrieval_contents")
    if isinstance(raw_retrievals, list):
        for rank, raw_item in enumerate(raw_retrievals[:top_n], start=1):
            if not isinstance(raw_item, dict):
                continue
            items.append(_normalize_single_item(rank=rank, raw_item=raw_item))

    if items:
        return items

    raw_attributions = payload.get("attributions")
    if isinstance(raw_attributions, list):
        for rank, raw_item in enumerate(raw_attributions[:top_n], start=1):
            if not isinstance(raw_item, dict):
                continue
            items.append(_normalize_single_item(rank=rank, raw_item=raw_item))
    return items


def normalize_filename(value: str) -> str:
    """Normalize a filename for robust matching."""

    normalized = unicodedata.normalize("NFKC", value or "")
    name_only = Path(normalized).name
    return name_only.strip().casefold()


def anchor_text_matches(*, anchor_text: str, snippet: str | None, threshold: int) -> bool:
    """Return whether the anchor text matches a retrieved snippet above the threshold."""

    if not anchor_text.strip() or not snippet or not snippet.strip():
        return False

    anchor_normalized = _normalize_text(anchor_text)
    snippet_normalized = _normalize_text(snippet)
    if anchor_normalized in snippet_normalized:
        return True
    score = SequenceMatcher(None, anchor_normalized, snippet_normalized).ratio() * 100
    return score >= float(threshold)


def _normalize_single_item(*, rank: int, raw_item: dict[str, Any]) -> NormalizedRetrievalItem:
    filename = (
        _extract_filename(raw_item)
        or ""
    )
    page = _extract_page(raw_item)
    snippet = _extract_snippet(raw_item)
    score = _extract_score(raw_item)
    return NormalizedRetrievalItem(
        rank=rank,
        filename=filename,
        normalized_filename=normalize_filename(filename),
        page=page,
        snippet=snippet,
        score=score,
    )


def _extract_filename(item: dict[str, Any]) -> str:
    for key in ("filename", "file_name", "document_name", "document_filename", "source_file"):
        value = item.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()

    metadata = item.get("metadata")
    if isinstance(metadata, dict):
        for key in ("filename", "file_name", "title", "source_file"):
            value = metadata.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()

    source_value = item.get("source")
    if isinstance(source_value, str) and source_value.strip():
        return source_value.strip()
    return ""


def _extract_page(item: dict[str, Any]) -> int | None:
    for key in ("page", "page_number", "page_num", "start_page"):
        value = item.get(key)
        parsed = _coerce_positive_int(value)
        if parsed is not None:
            return parsed

    metadata = item.get("metadata")
    if isinstance(metadata, dict):
        for key in ("page", "page_number", "page_num", "start_page"):
            parsed = _coerce_positive_int(metadata.get(key))
            if parsed is not None:
                return parsed
    return None


def _extract_snippet(item: dict[str, Any]) -> str | None:
    for key in ("snippet", "content", "text", "chunk_text"):
        value = item.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()

    metadata = item.get("metadata")
    if isinstance(metadata, dict):
        for key in ("snippet", "content", "text", "anchor_text"):
            value = metadata.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return None


def _extract_score(item: dict[str, Any]) -> float | None:
    for key in ("score", "similarity", "relevance_score", "rerank_score"):
        value = item.get(key)
        if isinstance(value, (int, float)):
            return float(value)
    return None


def _coerce_positive_int(value: Any) -> int | None:
    if isinstance(value, int) and value > 0:
        return value
    if isinstance(value, str) and value.strip().isdigit():
        parsed = int(value.strip())
        return parsed if parsed > 0 else None
    return None


def _normalize_text(value: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", value).casefold().split())

