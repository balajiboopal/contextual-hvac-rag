"""Helpers for converting model output into WhatsApp-friendly text."""

from __future__ import annotations

import re

CITATION_PATTERN = re.compile(r"\[(\d+)\]\([^)]*\)")
BROKEN_CITATION_PATTERN = re.compile(r"(?:[0-9¹²³⁴⁵⁶⁷⁸⁹⁰]+\(\))+")
MARKDOWN_HEADING_PATTERN = re.compile(r"^#{1,6}\s+(.+?)\s*$")
STAR_HEADING_PATTERN = re.compile(r"^\*{1,2}(.+?)\*{1,2}$")
TABLE_SEPARATOR_PATTERN = re.compile(r"^\|?\s*[:\-| ]+\|?\s*$")
LEADING_BULLET_PATTERN = re.compile(r"^(?:[.\-•·●▪■□▣]|â€¢)\s+")
STAR_TOKEN_PATTERN = re.compile(r"\*{1,2}([^*]+?)\*{1,2}")
INLINE_BULLET_SPLIT_PATTERN = re.compile(r"\s*[•·]\s*")
EMPTY_CITATION_PATTERN = re.compile(r"\[\]")
SENTENCE_SPLIT_PATTERN = re.compile(r"(?<=[.!?])\s+")
BULLETED_HEADING_PATTERN = re.compile(r"^-\s+\*{1,2}(.+?)\*{1,2}$")


def format_for_whatsapp(text: str) -> str:
    """Convert markdown-heavy answer text into plain WhatsApp-friendly text."""

    if not text.strip():
        return ""

    cleaned_text = CITATION_PATTERN.sub("", text)
    cleaned_text = BROKEN_CITATION_PATTERN.sub("", cleaned_text)
    cleaned_text = EMPTY_CITATION_PATTERN.sub("", cleaned_text)
    cleaned_text = re.sub(r" {2,}", " ", cleaned_text)
    output_lines: list[str] = []
    pending_table_header: str | None = None
    pending_step_number: str | None = None
    in_table_body = False

    for raw_line in cleaned_text.splitlines():
        line = raw_line.strip()
        if not line:
            if pending_step_number is not None:
                output_lines.append(f"{pending_step_number}.")
                pending_step_number = None
            if pending_table_header:
                _append_heading(output_lines, pending_table_header)
                pending_table_header = None
                in_table_body = False
            if output_lines and output_lines[-1] != "":
                output_lines.append("")
            continue

        heading_match = MARKDOWN_HEADING_PATTERN.match(line)
        if heading_match:
            if pending_step_number is not None:
                output_lines.append(f"{pending_step_number}.")
                pending_step_number = None
            if pending_table_header:
                _append_heading(output_lines, pending_table_header)
                pending_table_header = None
                in_table_body = False
            _append_heading(output_lines, heading_match.group(1).strip())
            continue

        special_heading = _extract_tableish_heading(line)
        if special_heading:
            if pending_step_number is not None:
                output_lines.append(f"{pending_step_number}.")
                pending_step_number = None
            if pending_table_header:
                _append_heading(output_lines, pending_table_header)
                pending_table_header = None
                in_table_body = False
            _append_heading(output_lines, special_heading)
            continue

        star_heading_match = STAR_HEADING_PATTERN.match(line)
        if star_heading_match:
            if pending_step_number is not None:
                output_lines.append(f"{pending_step_number}.")
                pending_step_number = None
            if pending_table_header:
                _append_heading(output_lines, pending_table_header)
                pending_table_header = None
                in_table_body = False
            _append_heading(output_lines, star_heading_match.group(1).strip())
            continue

        if "|" in line and (line.startswith("|") or line.endswith("|")):
            if pending_step_number is not None:
                output_lines.append(f"{pending_step_number}.")
                pending_step_number = None
            cells = [cell.strip() for cell in line.strip("|").split("|")]
            cells = [cell for cell in cells if cell]
            if not cells:
                continue
            if TABLE_SEPARATOR_PATTERN.match(line):
                if pending_table_header:
                    _append_heading(output_lines, pending_table_header)
                    pending_table_header = None
                in_table_body = True
                continue
            if len(cells) == 1:
                if pending_table_header is None and not in_table_body:
                    pending_table_header = cells[0]
                else:
                    output_lines.append(_normalize_bullets(cells[0]))
                continue
            header_heading = _extract_pipe_header_heading(cells)
            if header_heading is not None:
                if header_heading:
                    _append_heading(output_lines, header_heading)
                in_table_body = True
                continue
            pipe_rows = _format_pipe_table_row(
                [_normalize_bullets(cell) for cell in cells],
            )
            if pipe_rows is not None:
                output_lines.extend(pipe_rows)
                in_table_body = True
                continue
            output_lines.append(" - ".join(_normalize_bullets(cell) for cell in cells))
            in_table_body = True
            continue

        if pending_table_header:
            _append_heading(output_lines, pending_table_header)
            pending_table_header = None
        in_table_body = False

        normalized_line = _normalize_bullets(line)
        if _is_generic_table_label(normalized_line):
            continue
        numeric_step = _extract_numeric_step(normalized_line)
        if numeric_step is not None:
            pending_step_number = numeric_step
            continue
        if pending_step_number is not None:
            output_lines.append(f"{pending_step_number}. {normalized_line}")
            pending_step_number = None
            continue
        structured_rows = _format_task_style_row(normalized_line)
        if structured_rows is not None:
            output_lines.extend(structured_rows)
            continue
        bulleted_heading_match = BULLETED_HEADING_PATTERN.match(normalized_line)
        if bulleted_heading_match:
            _append_heading(output_lines, bulleted_heading_match.group(1).strip())
            continue
        if _is_heading_like(normalized_line):
            _append_heading(output_lines, normalized_line.rstrip(":"))
            continue
        output_lines.append(normalized_line)

    if pending_table_header:
        _append_heading(output_lines, pending_table_header)
    if pending_step_number is not None:
        output_lines.append(f"{pending_step_number}.")

    return _collapse_blank_lines(output_lines)


def format_reply_chunks(text: str, *, max_chars: int = 1200) -> list[str]:
    """Format a reply and split it into WhatsApp-friendly chunks."""

    formatted = format_for_whatsapp(text)
    if not formatted:
        return []

    limit = max(80, max_chars)
    paragraphs = [part.strip() for part in formatted.split("\n\n") if part.strip()]
    chunks: list[str] = []
    current = ""

    for paragraph in paragraphs:
        for part in _split_paragraph_for_limit(paragraph, limit):
            candidate = part if not current else f"{current}\n\n{part}"
            if len(candidate) <= limit:
                current = candidate
                continue
            if current:
                chunks.append(current)
            current = part

    if current:
        chunks.append(current)

    return chunks


def _normalize_bullets(line: str) -> str:
    """Normalize a single line for WhatsApp display."""

    stripped = line.strip().strip("|").strip()
    if " | " in stripped:
        stripped = " - ".join(part.strip() for part in stripped.split("|") if part.strip())
    if stripped.startswith("✓") or stripped.startswith("âœ“"):
        return f"- {stripped.lstrip('✓âœ“').strip()}"
    if stripped.startswith("- [ ]"):
        return f"- {stripped[5:].strip()}"
    if LEADING_BULLET_PATTERN.match(stripped):
        return f"- {LEADING_BULLET_PATTERN.sub('', stripped).strip()}"
    return stripped


def _is_heading_like(line: str) -> bool:
    """Return whether a line reads like a section heading."""

    if not line or line.startswith("- ") or re.match(r"^\d+\.\s+", line):
        return False
    if len(line) > 90:
        return False
    return line.endswith(":")


def _is_generic_table_label(line: str) -> bool:
    """Return whether a line is a generic table label that should be suppressed."""

    normalized = line.strip().lstrip("-").strip().rstrip(".:").casefold()
    return normalized in {
        "action",
        "actions",
        "details",
        "frequency",
        "frequency description",
        "key requirements and standards",
        "specific details",
        "step",
        "steps",
    }


def _extract_numeric_step(line: str) -> str | None:
    """Return a bare step number when a line only contains a numbered marker."""

    match = re.fullmatch(r"-?\s*(\d{1,3})[.)]?", line.strip())
    if match:
        return match.group(1)
    return None


def _append_heading(output_lines: list[str], heading_text: str) -> None:
    """Append a heading with clear visual separation."""

    if output_lines and output_lines[-1] != "":
        output_lines.append("")
    output_lines.append(f"*{heading_text.strip()}*")
    output_lines.append("")


def _extract_tableish_heading(line: str) -> str | None:
    """Convert a table-style header row into a single section heading."""

    star_tokens = [token.strip() for token in STAR_TOKEN_PATTERN.findall(line) if token.strip()]
    if len(star_tokens) >= 2:
        heading = star_tokens[0]
        if heading.casefold().endswith(" task"):
            heading = f"{heading}s"
        return heading

    if " - " not in line:
        return None
    parts = [part.strip() for part in line.split(" - ") if part.strip()]
    if len(parts) != 2:
        return None
    left, right = parts
    right_normalized = right.casefold().replace("/", " ")
    if "frequency" in right_normalized or "description" in right_normalized or "details" in right_normalized:
        heading = left
        if heading.casefold().endswith(" task"):
            heading = f"{heading}s"
        return heading
    return None


def _extract_pipe_header_heading(cells: list[str]) -> str | None:
    """Treat common two-column table headers as section headings instead of content."""

    if len(cells) != 2:
        return None

    left = _normalize_bullets(cells[0]).strip()
    right = _normalize_bullets(cells[1]).strip()
    left_normalized = left.casefold()
    right_normalized = right.casefold().replace("/", " ")

    if (
        left_normalized in {"step", "steps", "task", "tasks", "category"}
        and right_normalized in {
            "action",
            "actions",
            "details",
            "description",
            "frequency description",
            "specific details",
            "key requirements and standards",
        }
    ):
        return ""

    if any(
        keyword in right_normalized
        for keyword in ("details", "requirements", "actions", "description", "frequency", "standards")
    ):
        return left

    return None


def _format_task_style_row(line: str) -> list[str] | None:
    """Convert a task-style row into a bullet title plus detail line."""

    if " - " not in line:
        return None
    if line.startswith("- ") or re.match(r"^\d+\.\s+", line):
        return None

    parts = [part.strip() for part in line.split(" - ") if part.strip()]
    if len(parts) < 2:
        return None

    title = parts[0]
    if len(title) > 50:
        return None

    if title.casefold() in {"task", "maintenance task", "frequency/description"}:
        return None

    detail = ". ".join(parts[1:])
    if not detail.endswith((".", "!", "?")):
        detail = f"{detail}."
    return [f"- {title}", f"  {detail}"]


def _format_pipe_table_row(cells: list[str]) -> list[str] | None:
    """Convert common two-column table rows into chat-native bullets."""

    if len(cells) < 2:
        return None

    title = cells[0].strip()
    if not title or len(title) > 80:
        return None

    detail_segments: list[str] = []
    for cell in cells[1:]:
        detail_segments.extend(_split_detail_items(cell))

    detail_segments = [segment for segment in detail_segments if segment]
    if not detail_segments:
        return [f"- {title}"]

    if len(detail_segments) == 1:
        return [f"- {title}", f"  {detail_segments[0]}"]

    lines = [f"- {title}"]
    lines.extend(f"  - {segment}" for segment in detail_segments)
    return lines


def _split_detail_items(detail: str) -> list[str]:
    """Split a table detail cell into one or more readable detail lines."""

    compact = detail.strip()
    if not compact:
        return []

    pieces = [piece.strip() for piece in INLINE_BULLET_SPLIT_PATTERN.split(compact) if piece.strip()]
    if not pieces:
        pieces = [compact]

    normalized: list[str] = []
    for piece in pieces:
        cleaned = piece.strip()
        if not cleaned:
            continue
        if cleaned.startswith("- "):
            cleaned = cleaned[2:].strip()
        if not cleaned.endswith((".", "!", "?")):
            cleaned = f"{cleaned}."
        normalized.append(cleaned)
    return normalized


def _split_paragraph_for_limit(paragraph: str, limit: int) -> list[str]:
    """Split a long paragraph into smaller message-safe parts."""

    if len(paragraph) <= limit:
        return [paragraph]

    lines = [line.strip() for line in paragraph.splitlines() if line.strip()]
    if len(lines) > 1:
        return _merge_units_with_limit(lines, limit)

    sentences = [part.strip() for part in SENTENCE_SPLIT_PATTERN.split(paragraph) if part.strip()]
    if len(sentences) > 1:
        return _merge_units_with_limit(sentences, limit)

    return [
        paragraph[index:index + limit].strip()
        for index in range(0, len(paragraph), limit)
        if paragraph[index:index + limit].strip()
    ]


def _merge_units_with_limit(units: list[str], limit: int) -> list[str]:
    """Merge smaller units into chunks without exceeding the limit."""

    chunks: list[str] = []
    current = ""
    for unit in units:
        separator = "\n" if current else ""
        candidate = f"{current}{separator}{unit}"
        if len(candidate) <= limit:
            current = candidate
            continue
        if current:
            chunks.append(current)
        if len(unit) <= limit:
            current = unit
            continue
        chunks.extend(_split_paragraph_for_limit(unit, limit))
        current = ""

    if current:
        chunks.append(current)
    return chunks


def _collapse_blank_lines(lines: list[str]) -> str:
    """Collapse repeated blank lines and return the final message."""

    normalized_lines: list[str] = []
    previous_blank = False
    for line in lines:
        is_blank = line == ""
        if is_blank and previous_blank:
            continue
        normalized_lines.append(line)
        previous_blank = is_blank
    return "\n".join(normalized_lines).strip()
