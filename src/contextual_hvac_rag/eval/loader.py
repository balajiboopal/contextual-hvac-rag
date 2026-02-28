"""CSV loading helpers for the evaluation pipeline."""

from __future__ import annotations

import ast
import csv
import hashlib
from dataclasses import dataclass
from pathlib import Path

EXPECTED_COLUMNS = [
    "Question",
    "gold_sources",
    "metadata",
    "page_range",
    "anchor_text",
]


@dataclass(frozen=True, slots=True)
class GoldenDatasetRow:
    """A normalized row from the golden-dataset CSV."""

    row_index: int
    question_id: str
    question: str
    gold_source: str
    difficulty: str
    gold_pages: list[int]
    anchor_text: str


def load_golden_dataset(csv_path: Path) -> list[GoldenDatasetRow]:
    """Load and validate the golden-dataset CSV."""

    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != EXPECTED_COLUMNS:
            raise ValueError(
                "Golden dataset must use the exact columns: "
                + ", ".join(EXPECTED_COLUMNS)
            )

        rows: list[GoldenDatasetRow] = []
        for row_index, raw_row in enumerate(reader):
            question = (raw_row.get("Question") or "").strip()
            gold_source = (raw_row.get("gold_sources") or "").strip()
            difficulty = (raw_row.get("metadata") or "").strip()
            anchor_text = (raw_row.get("anchor_text") or "").strip()
            question_id = stable_question_id(row_index=row_index, question=question)
            rows.append(
                GoldenDatasetRow(
                    row_index=row_index,
                    question_id=question_id,
                    question=question,
                    gold_source=gold_source,
                    difficulty=difficulty,
                    gold_pages=parse_page_range(raw_row.get("page_range") or ""),
                    anchor_text=anchor_text,
                )
            )
    return rows


def parse_page_range(raw_value: str) -> list[int]:
    """Parse a page range string like '[19]' or '[29,30,31]' into integers."""

    value = raw_value.strip()
    if not value:
        return []

    try:
        parsed = ast.literal_eval(value)
    except (SyntaxError, ValueError):
        return []

    if isinstance(parsed, int):
        return [parsed] if parsed > 0 else []
    if not isinstance(parsed, list):
        return []

    output: list[int] = []
    for item in parsed:
        if isinstance(item, int) and item > 0:
            output.append(item)
    return output


def stable_question_id(*, row_index: int, question: str) -> str:
    """Generate a stable question identifier from row index and question text."""

    digest = hashlib.sha1(f"{row_index}:{question}".encode("utf-8")).hexdigest()
    return digest[:16]

