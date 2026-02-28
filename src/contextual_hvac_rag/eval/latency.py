"""Latency extraction and aggregation helpers."""

from __future__ import annotations

import math
from typing import Any


LATENCY_KEYS = ("total", "embed", "search", "rerank", "generate")


def extract_latency_ms(*, payload: dict[str, Any], total_elapsed_ms: float) -> dict[str, float | None]:
    """Extract total and best-effort stage timing fields in milliseconds."""

    timings: dict[str, float | None] = {
        "total": round(total_elapsed_ms, 3),
        "embed": None,
        "search": None,
        "rerank": None,
        "generate": None,
    }

    workflow_trace = payload.get("workflow_trace")
    if not isinstance(workflow_trace, list):
        return timings

    for entry in workflow_trace:
        if not isinstance(entry, dict):
            continue
        raw_name = entry.get("name")
        raw_duration = entry.get("duration")
        if not isinstance(raw_name, str) or not isinstance(raw_duration, (int, float)):
            continue
        stage_name = classify_stage_name(raw_name)
        if stage_name is None:
            continue
        duration_ms = float(raw_duration) * 1000.0
        if timings[stage_name] is None:
            timings[stage_name] = 0.0
        timings[stage_name] = round((timings[stage_name] or 0.0) + duration_ms, 3)
    return timings


def summarize_latencies(latencies: list[dict[str, float | None]]) -> dict[str, dict[str, float | None]]:
    """Compute mean, p50, and p95 for each latency field."""

    summary: dict[str, dict[str, float | None]] = {}
    for key in LATENCY_KEYS:
        values = [entry[key] for entry in latencies if entry.get(key) is not None]
        numeric_values = [float(value) for value in values if isinstance(value, (int, float))]
        if not numeric_values:
            summary[key] = {"mean": None, "p50": None, "p95": None}
            continue
        summary[key] = {
            "mean": round(sum(numeric_values) / len(numeric_values), 3),
            "p50": round(_percentile(numeric_values, 50), 3),
            "p95": round(_percentile(numeric_values, 95), 3),
        }
    return summary


def classify_stage_name(step_name: str) -> str | None:
    """Map a workflow-trace step name to a normalized latency stage."""

    normalized = step_name.casefold()
    if "embed" in normalized:
        return "embed"
    if "rerank" in normalized:
        return "rerank"
    if "search" in normalized or "retriev" in normalized or "vector" in normalized:
        return "search"
    if "generate" in normalized or "llm" in normalized or "model" in normalized:
        return "generate"
    return None


def _percentile(values: list[float], percentile: int) -> float:
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    rank = (percentile / 100) * (len(ordered) - 1)
    lower_index = math.floor(rank)
    upper_index = math.ceil(rank)
    if lower_index == upper_index:
        return ordered[lower_index]
    lower_value = ordered[lower_index]
    upper_value = ordered[upper_index]
    fraction = rank - lower_index
    return lower_value + (upper_value - lower_value) * fraction

