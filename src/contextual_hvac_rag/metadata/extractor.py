"""PDF metadata extraction utilities."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Iterable

import fitz

TYPE_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("service manual", re.compile(r"\bservice\s+manual\b", re.IGNORECASE)),
    ("installation manual", re.compile(r"\binstallation\s+manual\b", re.IGNORECASE)),
    ("user manual", re.compile(r"\b(user|owner(?:'s)?)\s+manual\b", re.IGNORECASE)),
    ("parts list", re.compile(r"\bparts?\s+(list|catalog)\b", re.IGNORECASE)),
    ("wiring diagram", re.compile(r"\bwiring\s+diagram\b", re.IGNORECASE)),
)
VERSION_PATTERN = re.compile(
    r"\b(?:version|ver(?:sion)?|rev(?:ision)?)\s*[:#-]?\s*([A-Z0-9][A-Z0-9._-]{0,24})",
    re.IGNORECASE,
)
DATE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(
        r"\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\s+\d{4}\b",
        re.IGNORECASE,
    ),
    re.compile(r"\b\d{4}-\d{2}-\d{2}\b"),
    re.compile(r"\b\d{1,2}/\d{4}\b"),
    re.compile(r"\b\d{1,2}/\d{1,2}/\d{2,4}\b"),
)
DOT_LEADER_PATTERN = re.compile(r"\.{2,}\s*\d+\s*$")
FALSE_POSITIVE_PATTERN = re.compile(
    r"\b(contact|customer service|www\.|phone|email)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True, slots=True)
class ExtractedMetadata:
    """Normalized metadata derived from a PDF document."""

    doc_sha256: str
    title: str
    document_type: str
    version: str
    date: str
    source: str
    toc_pages: tuple[int, ...]
    index_pages: tuple[int, ...]
    toc_preview: str
    index_preview: str


def extract_pdf_metadata(pdf_bytes: bytes, *, source_label: str = "upload") -> ExtractedMetadata:
    """Extract stable metadata from PDF bytes."""

    doc_sha256 = sha256_bytes(pdf_bytes)
    with fitz.open(stream=pdf_bytes, filetype="pdf") as document:
        page_texts = [page.get_text("text") for page in document]
        title = extract_title(document, page_texts)
        front_matter = normalize_whitespace(" ".join(page_texts[: min(5, len(page_texts))]))
        document_type = classify_document_type(front_matter)
        version = extract_first_match(VERSION_PATTERN, front_matter)
        date = extract_date(front_matter)
        toc_pages = detect_reference_pages(page_texts, target="toc")
        index_pages = detect_reference_pages(page_texts, target="index")
        toc_preview = build_preview(page_texts, toc_pages)
        index_preview = build_preview(page_texts, index_pages)

    return ExtractedMetadata(
        doc_sha256=doc_sha256,
        title=title,
        document_type=document_type,
        version=version,
        date=date,
        source=source_label,
        toc_pages=toc_pages,
        index_pages=index_pages,
        toc_preview=toc_preview,
        index_preview=index_preview,
    )


def sha256_bytes(data: bytes) -> str:
    """Return the SHA-256 digest for raw bytes."""

    return hashlib.sha256(data).hexdigest()


def extract_title(document: fitz.Document, page_texts: list[str]) -> str:
    """Extract a best-effort title from the first page using large font spans."""

    if not document.page_count:
        return "Untitled Document"

    first_page = document.load_page(0)
    text_dict = first_page.get_text("dict")
    spans: list[tuple[float, str]] = []
    for block in text_dict.get("blocks", []):
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                text = normalize_whitespace(str(span.get("text", "")))
                size = float(span.get("size", 0.0))
                if text and len(text) > 3:
                    spans.append((size, text))

    if spans:
        max_size = max(size for size, _ in spans)
        title_parts: list[str] = []
        for size, text in sorted(spans, key=lambda item: item[0], reverse=True):
            if size < max_size - 0.3:
                continue
            if text not in title_parts:
                title_parts.append(text)
            if len(title_parts) == 3:
                break
        if title_parts:
            return " ".join(title_parts)[:240]

    first_page_text = page_texts[0] if page_texts else ""
    first_line = first_page_text.splitlines()[0].strip() if first_page_text else ""
    return first_line[:240] if first_line else "Untitled Document"


def classify_document_type(text: str) -> str:
    """Infer the manual type from leading document text."""

    for label, pattern in TYPE_PATTERNS:
        if pattern.search(text):
            return label
    return "technical document"


def extract_first_match(pattern: re.Pattern[str], text: str) -> str:
    """Return the first capture group for the given pattern, if present."""

    match = pattern.search(text)
    if not match:
        return ""
    return normalize_whitespace(match.group(1))


def extract_date(text: str) -> str:
    """Return the first date-like string found in the document preamble."""

    for pattern in DATE_PATTERNS:
        match = pattern.search(text)
        if match:
            return normalize_whitespace(match.group(0))
    return ""


def detect_reference_pages(page_texts: list[str], *, target: str) -> tuple[int, ...]:
    """Detect likely table-of-contents or index pages using heuristic scoring."""

    if target not in {"toc", "index"}:
        raise ValueError("target must be 'toc' or 'index'")

    total_pages = len(page_texts)
    if total_pages == 0:
        return ()

    if target == "toc":
        candidate_indices = range(0, min(12, total_pages))
        keywords = ("table of contents", "\ncontents\n", " contents ")
    else:
        start = max(total_pages - 12, 0)
        candidate_indices = range(start, total_pages)
        keywords = ("\nindex\n", " index ", "alphabetical")

    scored_pages: list[tuple[int, int]] = []
    for page_index in candidate_indices:
        text = page_texts[page_index]
        lowered = text.lower()
        score = 0
        if any(keyword in lowered for keyword in keywords):
            score += 4
        dot_leader_lines = sum(1 for line in text.splitlines() if DOT_LEADER_PATTERN.search(line))
        score += min(dot_leader_lines, 5)
        if FALSE_POSITIVE_PATTERN.search(text):
            score -= 3
        if target == "index" and re.search(r"\b[a-z]\s+\d+\b", lowered):
            score += 1
        if score >= 4:
            scored_pages.append((page_index + 1, score))

    return tuple(page for page, _ in sorted(scored_pages, key=lambda item: (-item[1], item[0]))[:3])


def build_preview(page_texts: list[str], pages: Iterable[int]) -> str:
    """Build a short preview snippet from the first detected page."""

    page_list = list(pages)
    if not page_list:
        return ""
    page_number = page_list[0]
    if page_number < 1 or page_number > len(page_texts):
        return ""
    return normalize_whitespace(page_texts[page_number - 1])[:280]


def normalize_whitespace(text: str) -> str:
    """Collapse repeated whitespace to a single space."""

    return re.sub(r"\s+", " ", text).strip()
