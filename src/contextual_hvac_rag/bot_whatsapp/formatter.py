"""Helpers for converting model output into WhatsApp-friendly text."""

from __future__ import annotations

import re

CITATION_PATTERN = re.compile(r"\[(\d+)\]\([^)]*\)")
MARKDOWN_HEADING_PATTERN = re.compile(r"^#{1,6}\s+(.+?)\s*$")
TABLE_SEPARATOR_PATTERN = re.compile(r"^\|?\s*[:\-| ]+\|?\s*$")


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
                output_lines.append(f"*{pending_table_header}*")
                pending_table_header = None
                in_table_body = False
            if output_lines and output_lines[-1] != "":
                output_lines.append("")
            continue

        heading_match = MARKDOWN_HEADING_PATTERN.match(line)
        if heading_match:
            if pending_table_header:
                output_lines.append(f"*{pending_table_header}*")
                pending_table_header = None
                in_table_body = False
            output_lines.append(f"*{heading_match.group(1).strip()}*")
            continue

        if line.startswith("|") and line.endswith("|"):
            cells = [cell.strip() for cell in line.strip("|").split("|")]
            cells = [cell for cell in cells if cell]
            if not cells:
                continue
            if TABLE_SEPARATOR_PATTERN.match(line):
                if pending_table_header:
                    output_lines.append(f"*{pending_table_header}*")
                    output_lines.append("")
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
            output_lines.append(f"*{pending_table_header}*")
            output_lines.append("")
            pending_table_header = None
        in_table_body = False

        output_lines.append(_normalize_bullets(line))

    if pending_table_header:
        output_lines.append(f"*{pending_table_header}*")

    return _collapse_blank_lines(output_lines)


def _normalize_bullets(line: str) -> str:
    """Normalize a single line for WhatsApp display."""

    if line.startswith("✓"):
        return f"- {line.lstrip('✓').strip()}"
    if line.startswith("- [ ]"):
        return f"- {line[5:].strip()}"
    return line


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
