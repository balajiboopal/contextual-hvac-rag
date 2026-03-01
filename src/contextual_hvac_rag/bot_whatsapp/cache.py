"""Short-lived in-memory caching for repeated WhatsApp questions."""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
from time import monotonic
from typing import Any
from unicodedata import normalize


@dataclass(frozen=True, slots=True)
class CachedAgentResponse:
    """Serializable subset of an agent response safe to reuse for one user."""

    answer_text: str
    attributions: list[dict[str, Any]]
    retrieval_contents: list[dict[str, Any]]


class ResponseCache:
    """A tiny TTL cache used to skip repeated identical queries for one WhatsApp user."""

    def __init__(self, *, ttl_seconds: int, max_entries: int = 256) -> None:
        self._ttl_seconds = max(0, ttl_seconds)
        self._max_entries = max(1, max_entries)
        self._entries: OrderedDict[str, tuple[float, CachedAgentResponse]] = OrderedDict()
        self._hits = 0
        self._misses = 0

    def get(self, key: str, *, now: float | None = None) -> CachedAgentResponse | None:
        """Return a cached entry if it exists and has not expired."""

        current_time = monotonic() if now is None else now
        self._purge_expired(current_time)
        entry = self._entries.get(key)
        if entry is None:
            self._misses += 1
            return None
        expires_at, cached_response = entry
        if expires_at <= current_time:
            self._entries.pop(key, None)
            self._misses += 1
            return None
        self._entries.move_to_end(key)
        self._hits += 1
        return cached_response

    def set(self, key: str, value: CachedAgentResponse, *, now: float | None = None) -> None:
        """Store a cached entry if caching is enabled."""

        if self._ttl_seconds <= 0:
            return

        current_time = monotonic() if now is None else now
        self._purge_expired(current_time)
        self._entries[key] = (current_time + self._ttl_seconds, value)
        self._entries.move_to_end(key)

        while len(self._entries) > self._max_entries:
            self._entries.popitem(last=False)

    def _purge_expired(self, current_time: float) -> None:
        expired_keys = [
            key
            for key, (expires_at, _) in self._entries.items()
            if expires_at <= current_time
        ]
        for key in expired_keys:
            self._entries.pop(key, None)

    def stats(self) -> dict[str, int]:
        """Return lightweight cache stats for health/debug output."""

        return {
            "entries": len(self._entries),
            "hits": self._hits,
            "misses": self._misses,
            "ttl_seconds": self._ttl_seconds,
        }


def build_cache_key(*, wa_id: str, text: str) -> str:
    """Return a stable per-user cache key for repeated text-only questions."""

    normalized_text = " ".join(normalize("NFKC", text).casefold().split())
    return f"{wa_id}:{normalized_text}"
