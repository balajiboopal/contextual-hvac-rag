"""Retrieval metric calculations."""

from __future__ import annotations

import math
from typing import Sequence


def recall_at_k(relevances: Sequence[int], k: int) -> float:
    """Return binary recall@k for a single query."""

    if any(value > 0 for value in relevances[:k]):
        return 1.0
    return 0.0


def mrr_at_k(relevances: Sequence[int], k: int) -> float:
    """Return reciprocal rank@k for a single query."""

    for index, value in enumerate(relevances[:k], start=1):
        if value > 0:
            return 1.0 / index
    return 0.0


def ndcg_at_k(relevances: Sequence[int], k: int) -> float:
    """Return nDCG@k for binary or graded relevance values."""

    truncated = list(relevances[:k])
    if not truncated:
        return 0.0

    dcg_value = _dcg(truncated)
    if dcg_value == 0.0:
        return 0.0

    ideal_relevances = sorted(truncated, reverse=True)
    ideal_dcg = _dcg(ideal_relevances)
    if ideal_dcg == 0.0:
        return 0.0
    return dcg_value / ideal_dcg


def average(values: Sequence[float]) -> float:
    """Return the arithmetic mean for a non-empty sequence."""

    if not values:
        return 0.0
    return sum(values) / len(values)


def _dcg(relevances: Sequence[int]) -> float:
    total = 0.0
    for index, value in enumerate(relevances, start=1):
        gain = float(value)
        total += gain / math.log2(index + 1)
    return total

