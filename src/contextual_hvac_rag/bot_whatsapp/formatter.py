"""Helpers for converting model output into WhatsApp-friendly text."""

from __future__ import annotations

import re

CITATION_PATTERN = re.compile(r"\[(\d+)\]\([^)]*\)")
MARKDOWN_HEADING_PATTERN = re.compile(r"^#{1,6}\s+(.+?)\s*$")
STAR_HEADING_PATTERN = re.compile(r"^\*{1,2}(.+?)\*{1,2}$")
TABLE_SEPARATOR_PATTERN = re.compile(r"^\|?\s*[:\-| ]+\|?\s*$")
LEADING_BULLET_PATTERN = re.compile(r"^(?:[.\-•·●▪]|â€¢)\s+")
STAR_TOKEN_PATTERN = re.compile(r"\*{1,2}([^*]+?)\*{1,2}")


def format_for_whatsapp(text: str) -> str:
    """Convert markdown-heavy answer text into plain WhatsApp-friendly text."""

    if not text.strip():
        return ""

    cleaned_text = CITATION_PATTERN.sub("", text)
    output_lines: list[str] = []
    pending_table_header: str | None = None
    in_table_body = False

    for raw_line in cleaned_text.splitlines():
        line = raw_line.strip()
        if not line:
            if pending_table_header:
                _append_heading(output_lines, pending_table_header)
                pending_table_header = None
                in_table_body = False
            if output_lines and output_lines[-1] != "":
                output_lines.append("")
            continue

        heading_match = MARKDOWN_HEADING_PATTERN.match(line)
        if heading_match:
            if pending_table_header:
                _append_heading(output_lines, pending_table_header)
                pending_table_header = None
                in_table_body = False
            _append_heading(output_lines, heading_match.group(1).strip())
            continue

        special_heading = _extract_tableish_heading(line)
        if special_heading:
            if pending_table_header:
                _append_heading(output_lines, pending_table_header)
                pending_table_header = None
                in_table_body = False
            _append_heading(output_lines, special_heading)
            continue

        star_heading_match = STAR_HEADING_PATTERN.match(line)
        if star_heading_match:
            if pending_table_header:
                _append_heading(output_lines, pending_table_header)
                pending_table_header = None
                in_table_body = False
            _append_heading(output_lines, star_heading_match.group(1).strip())
            continue

        if "|" in line and (line.startswith("|") or line.endswith("|")):
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
            output_lines.append(" - ".join(_normalize_bullets(cell) for cell in cells))
            in_table_body = True
            continue

        if pending_table_header:
            _append_heading(output_lines, pending_table_header)
            pending_table_header = None
        in_table_body = False

        normalized_line = _normalize_bullets(line)
        structured_rows = _format_task_style_row(normalized_line)
        if structured_rows is not None:
            output_lines.extend(structured_rows)
            continue
        if _is_heading_like(normalized_line):
            _append_heading(output_lines, normalized_line.rstrip(":"))
            continue
        output_lines.append(normalized_line)

    if pending_table_header:
        _append_heading(output_lines, pending_table_header)

    return _collapse_blank_lines(output_lines)


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
