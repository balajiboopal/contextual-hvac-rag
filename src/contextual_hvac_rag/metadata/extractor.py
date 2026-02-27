"""PDF metadata extraction utilities ported from the original Colab workflow."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

import fitz

MONTHS = r"(jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*"
TYPE_PATTERNS: tuple[tuple[str, str], ...] = (
    ("service manual", r"\bservice\s+manual\b"),
    ("installation manual", r"\binstallation\s+manual\b"),
    ("user manual", r"\buser\s+manual\b"),
    ("technical bulletin", r"\btechnical\s+bulletin\b"),
    ("troubleshooting guide", r"\btroubleshooting\b"),
    ("specification", r"\bspec(ification)?s?\b"),
    ("resource guide", r"\bresource\s+guide\b"),
    ("report", r"\breport\b"),
    ("guide", r"\bguide\b"),
)
EXCLUDE_TOC_HEADERS: tuple[str, ...] = (
    r"\blist of figures\b",
    r"\blist of tables\b",
)
DOT_LEADER_COMPACT = re.compile(r"\.{2,}\s*\d{1,3}\s*$")
DOT_LEADER_SPACED = re.compile(r"(?:\.\s*){6,}\d{1,3}\s*$")
NUMBERED_WITH_PAGE = re.compile(r"^(\d+(\.\d+)*|[A-Z]\d*[\.\-]?)\s+.+\s(\d{1,3})\s*$")


@dataclass(frozen=True, slots=True)
class PageHit:
    """A scored page hit for TOC or index detection."""

    page: int
    score: int
    text: str


@dataclass(frozen=True, slots=True)
class ExtractedMetadata:
    """Normalized metadata derived from a PDF document."""

    doc_sha256: str
    title: str | None
    document_type: str | None
    version: str | None
    date: str | None
    source: str
    toc: tuple[PageHit, ...]
    index: tuple[PageHit, ...]


def extract_pdf_metadata(
    pdf_bytes: bytes,
    *,
    source_label: str = "upload",
    scan_first_pages: int = 25,
    scan_last_pages: int = 25,
    toc_threshold: int = 10,
    index_threshold: int = 12,
) -> ExtractedMetadata:
    """Extract stable metadata from PDF bytes using the original heuristic flow."""

    with fitz.open(stream=pdf_bytes, filetype="pdf") as document:
        total_pages = len(document)
        front_pages = list(range(min(total_pages, scan_first_pages)))
        back_pages = list(range(max(0, total_pages - scan_last_pages), total_pages))

        title: str | None = None
        document_type: str | None = None
        version: str | None = None
        publication_date: str | None = None

        for page_index in front_pages[:10]:
            page = document[page_index]
            text = page.get_text("text") or ""
            text_lower = text.lower()

            if page_index == 0:
                title = extract_title_from_first_page(page) or title

            if len(text.strip()) < 40:
                continue

            if document_type is None:
                document_type = extract_type(text_lower)
            if version is None:
                version = extract_version(text)
            if publication_date is None:
                publication_date = extract_date(text)

            if title and document_type and version and publication_date:
                break

        toc_hits: list[PageHit] = []
        for page_index in front_pages:
            text = document[page_index].get_text("text") or ""
            if len(text.strip()) < 50:
                continue
            score = toc_score(text)
            if score >= toc_threshold:
                toc_hits.append(
                    PageHit(page=page_index + 1, score=score, text=normalize_whitespace(text))
                )

        toc_hits.sort(key=lambda item: item.score, reverse=True)
        toc_pages: tuple[PageHit, ...] = ()
        if toc_hits:
            best_page = toc_hits[0].page
            nearby_hits = [hit for hit in toc_hits if abs(hit.page - best_page) <= 2]
            toc_pages = tuple(dedupe_page_hits(sorted(nearby_hits, key=lambda item: item.page)))

        index_hits: list[PageHit] = []
        for page_index in back_pages:
            text = document[page_index].get_text("text") or ""
            if len(text.strip()) < 50:
                continue
            score = index_score(text)
            if score >= index_threshold:
                index_hits.append(
                    PageHit(page=page_index + 1, score=score, text=normalize_whitespace(text))
                )

        index_hits.sort(key=lambda item: item.score, reverse=True)
        index_pages: tuple[PageHit, ...] = ()
        if index_hits:
            best_page = index_hits[0].page
            nearby_hits = [hit for hit in index_hits if abs(hit.page - best_page) <= 3]
            index_pages = tuple(dedupe_page_hits(sorted(nearby_hits, key=lambda item: item.page)))

    return ExtractedMetadata(
        doc_sha256=compute_doc_id_from_bytes(pdf_bytes),
        title=title,
        document_type=document_type,
        version=version,
        date=publication_date,
        source=source_label,
        toc=toc_pages,
        index=index_pages,
    )


def compute_doc_id_from_bytes(pdf_bytes: bytes) -> str:
    """Return a stable document id using SHA-256 of the raw PDF bytes."""

    return hashlib.sha256(pdf_bytes).hexdigest()


def normalize_whitespace(value: str) -> str:
    """Collapse repeated whitespace to a single space."""

    return re.sub(r"\s+", " ", value).strip()


def dedupe_page_hits(items: list[PageHit]) -> list[PageHit]:
    """Remove duplicate page hits while preserving the first occurrence."""

    seen_pages: set[int] = set()
    output: list[PageHit] = []
    for item in items:
        if item.page in seen_pages:
            continue
        output.append(item)
        seen_pages.add(item.page)
    return output


def looks_like_contact_or_imprint(text_lower: str) -> bool:
    """Detect contact-heavy pages so they are not mislabeled as TOC or index pages."""

    email_count = len(re.findall(r"\b[\w\.-]+@[\w\.-]+\.\w+\b", text_lower))
    url_count = len(re.findall(r"\bhttps?://|\bwww\.", text_lower))
    phone_like_count = len(re.findall(r"\+\d|\bT\s*\+?\d|\bF\s*\+?\d", text_lower))
    return (email_count + url_count + phone_like_count) >= 3


def extract_title_from_first_page(page: fitz.Page) -> str | None:
    """Infer a title from the first page by selecting the largest font spans."""

    text_dict = page.get_text("dict")
    spans: list[tuple[float, str]] = []
    for block in text_dict.get("blocks", []):
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                text = normalize_whitespace(str(span.get("text", "")))
                if len(text) < 6:
                    continue
                spans.append((float(span.get("size", 0.0)), text))

    if not spans:
        return None

    spans.sort(reverse=True, key=lambda item: item[0])
    top_size = spans[0][0]
    title_parts = [text for size, text in spans if size >= top_size - 0.5][:3]
    title = normalize_whitespace(" ".join(title_parts))
    return title[:200] if title else None


def extract_version(text: str) -> str | None:
    """Extract a revision or version string from page text."""

    patterns = (
        r"\b(rev(?:ision)?\.?\s*[A-Z0-9]+)\b",
        r"\b(version\s*\d+(\.\d+)*)\b",
        r"\b(v\s*\d+(\.\d+)*)\b",
    )
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return normalize_whitespace(match.group(1))
    return None


def extract_date(text: str) -> str | None:
    """Extract the first matching publication date from page text."""

    month_year_match = re.search(rf"\b({MONTHS})\s+(19|20)\d{{2}}\b", text, re.IGNORECASE)
    if month_year_match:
        return normalize_whitespace(month_year_match.group(0))

    year_match = re.search(r"\b(19|20)\d{2}\b", text)
    if year_match:
        return year_match.group(0)
    return None


def extract_type(text_lower: str) -> str | None:
    """Infer the document type from the leading text."""

    for label, pattern in TYPE_PATTERNS:
        if re.search(pattern, text_lower):
            return label
    return None


def toc_score(page_text: str) -> int:
    """Return a TOC likelihood score for a page."""

    if not page_text:
        return 0

    lines = [line.strip() for line in page_text.splitlines() if line.strip()]
    if len(lines) < 8:
        return 0

    text_lower = page_text.lower()
    if any(re.search(pattern, text_lower) for pattern in EXCLUDE_TOC_HEADERS):
        return 0
    if looks_like_contact_or_imprint(text_lower):
        return 0

    header_score = 0
    if re.search(r"\btable of contents\b", text_lower):
        header_score += 10
    elif re.search(r"^\s*contents?\s*$", text_lower, re.MULTILINE):
        header_score += 8
    elif re.search(r"^\s*content\s*$", text_lower, re.MULTILINE):
        header_score += 7
    elif "contents" in text_lower or "content" in text_lower:
        header_score += 2

    dot_leader_hits = 0
    numbered_hits = 0
    end_page_number_hits = 0
    for line in lines:
        if re.search(r"\s(\d{1,3})\s*$", line):
            end_page_number_hits += 1
        if DOT_LEADER_COMPACT.search(line) or DOT_LEADER_SPACED.search(line):
            dot_leader_hits += 1
        if NUMBERED_WITH_PAGE.match(line):
            numbered_hits += 1

    if dot_leader_hits + numbered_hits < 3:
        return 0

    return header_score + (2 * dot_leader_hits) + (2 * numbered_hits) + end_page_number_hits


def index_score(page_text: str) -> int:
    """Return an index likelihood score for a page."""

    if not page_text:
        return 0

    lines = [line.strip() for line in page_text.splitlines() if line.strip()]
    if len(lines) < 10:
        return 0

    text_lower = page_text.lower()
    if looks_like_contact_or_imprint(text_lower):
        return 0

    header_score = 0
    if re.search(r"^\s*index\s*$", text_lower, re.MULTILINE):
        header_score += 10
    elif "index" in text_lower:
        header_score += 2

    end_page_number_lines = 0
    for line in lines:
        if re.search(r"\s(\d{1,3})\s*$", line) and len(line) >= 8:
            end_page_number_lines += 1

    if end_page_number_lines < 5 and header_score < 10:
        return 0

    return header_score + end_page_number_lines
