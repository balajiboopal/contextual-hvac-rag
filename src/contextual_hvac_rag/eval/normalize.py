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
    value = _find_nested_value(
        item,
        keys=("filename", "file_name", "document_name", "document_filename", "source_file", "title"),
        expected_type=str,
    )
    if isinstance(value, str) and value.strip():
        return value.strip()
    return ""


def _extract_page(item: dict[str, Any]) -> int | None:
    value = _find_nested_value(
        item,
        keys=("page", "page_number", "page_num", "start_page"),
        expected_type=(int, str),
    )
    return _coerce_positive_int(value)


def _extract_snippet(item: dict[str, Any]) -> str | None:
    value = _find_nested_value(
        item,
        keys=("snippet", "content", "text", "chunk_text", "anchor_text"),
        expected_type=str,
    )
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _extract_score(item: dict[str, Any]) -> float | None:
    value = _find_nested_value(
        item,
        keys=("score", "similarity", "relevance_score", "rerank_score"),
        expected_type=(int, float),
    )
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


def _find_nested_value(
    item: dict[str, Any],
    *,
    keys: tuple[str, ...],
    expected_type: Any,
) -> Any:
    for key in keys:
        value = item.get(key)
        if isinstance(value, expected_type):
            return value

    for value in item.values():
        if isinstance(value, dict):
            nested_value = _find_nested_value(value, keys=keys, expected_type=expected_type)
            if nested_value is not None:
                return nested_value
        elif isinstance(value, list):
            for entry in value:
                if isinstance(entry, dict):
                    nested_value = _find_nested_value(entry, keys=keys, expected_type=expected_type)
                    if nested_value is not None:
                        return nested_value
    return None
