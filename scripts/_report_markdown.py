from __future__ import annotations

import re
from pathlib import Path


IMAGE_PATTERN = re.compile(r"^!\[(?P<alt>[^\]]*)\]\((?P<path>[^)]+)\)$")
ORDERED_LIST_PATTERN = re.compile(r"^(?P<indent>\s*)(?P<number>\d+)\.\s+(?P<text>.+)$")
UNORDERED_LIST_PATTERN = re.compile(r"^(?P<indent>\s*)[-*]\s+(?P<text>.+)$")
TABLE_SEPARATOR_PATTERN = re.compile(r"^:?-{3,}:?$")
REFERENCE_PLACEHOLDER_PATTERN_TEXT = (
    r"\[\[REF:(?P<target_kind>figure|table|equation|bibliography):"
    r"(?P<target_id>[A-Za-z0-9_]+)(?:\|(?P<prefix>[^\]]*))?\]\]"
)
REFERENCE_PLACEHOLDER_PATTERN = re.compile(REFERENCE_PLACEHOLDER_PATTERN_TEXT)
INLINE_EQUATION_PATTERN_TEXT = r"\$(?P<inline_latex>[^$\n]+)\$"
INLINE_TOKEN_PATTERN = re.compile(
    f"{REFERENCE_PLACEHOLDER_PATTERN_TEXT}|{INLINE_EQUATION_PATTERN_TEXT}"
)


def parse_image_block(line: str) -> dict[str, object] | None:
    match = IMAGE_PATTERN.match(line)
    if not match:
        return None
    alt = match.group("alt").strip() or "Image"
    path = match.group("path").strip()
    return {
        "kind": "image",
        "alt": alt,
        "path": path,
    }


def parse_list_item(raw_line: str) -> dict[str, object] | None:
    for pattern, ordered in (
        (ORDERED_LIST_PATTERN, True),
        (UNORDERED_LIST_PATTERN, False),
    ):
        match = pattern.match(raw_line.rstrip())
        if not match:
            continue
        indent = len(match.group("indent"))
        return {
            "kind": "list_item",
            "ordered": ordered,
            "number": int(match.group("number")) if ordered else None,
            "depth": min(indent // 2, 2),
            "text": match.group("text").strip(),
        }
    return None


def parse_pipe_row(line: str) -> list[str] | None:
    stripped = line.strip()
    if not stripped.startswith("|") or not stripped.endswith("|"):
        return None
    return [cell.strip() for cell in stripped.strip("|").split("|")]


def is_table_separator_row(cells: list[str]) -> bool:
    if not cells:
        return False
    return all(
        TABLE_SEPARATOR_PATTERN.fullmatch(cell.replace(" ", "")) for cell in cells
    )


def parse_simple_table(
    lines: list[str], start: int
) -> tuple[list[list[str]], int] | None:
    if start + 1 >= len(lines):
        return None
    header = parse_pipe_row(lines[start])
    separator = parse_pipe_row(lines[start + 1])
    if header is None or separator is None or len(header) != len(separator):
        return None
    if not is_table_separator_row(separator):
        return None

    rows = [header]
    consumed = 2
    index = start + 2
    while index < len(lines):
        cells = parse_pipe_row(lines[index])
        if cells is None:
            break
        normalized = (cells + [""] * len(header))[: len(header)]
        rows.append(normalized)
        consumed += 1
        index += 1
    return rows, consumed


def cross_reference_placeholder_text(segment: dict[str, object]) -> str:
    prefix = segment.get("prefix")
    suffix = f"|{prefix}" if prefix is not None else ""
    return (
        f"[[REF:{segment['target_kind']}:{segment['target_id']}{suffix}]]"
    )


def parse_paragraph_segments(text: str) -> list[dict[str, object]]:
    segments: list[dict[str, object]] = []
    cursor = 0
    for match in INLINE_TOKEN_PATTERN.finditer(text):
        if match.start() > cursor:
            segments.append({"kind": "text", "text": text[cursor : match.start()]})
        if match.group("inline_latex") is not None:
            segments.append(
                {
                    "kind": "inline_equation",
                    "latex": match.group("inline_latex"),
                }
            )
        else:
            prefix = match.group("prefix")
            segment = {
                "kind": "cross_reference",
                "target_kind": match.group("target_kind"),
                "target_id": match.group("target_id"),
            }
            if prefix is not None:
                segment["prefix"] = prefix
            segments.append(segment)
        cursor = match.end()
    if cursor < len(text):
        segments.append({"kind": "text", "text": text[cursor:]})
    return segments or [{"kind": "text", "text": text}]


def markdown_to_blocks(path: Path) -> list[dict[str, object]]:
    lines = path.read_text(encoding="utf-8").splitlines()
    blocks: list[dict[str, object]] = []
    paragraph_lines: list[str] = []
    code_lines: list[str] = []
    in_code_block = False
    code_language: str | None = None
    equation_index = 0

    def flush_paragraph() -> None:
        nonlocal paragraph_lines
        if paragraph_lines:
            text = " ".join(paragraph_lines)
            blocks.append(
                {
                    "kind": "paragraph",
                    "text": text,
                    "segments": parse_paragraph_segments(text),
                }
            )
            paragraph_lines = []

    def flush_code() -> None:
        nonlocal code_lines, code_language
        if code_lines:
            blocks.append(
                {
                    "kind": "code",
                    "text": "\n".join(code_lines),
                    "language": code_language,
                }
            )
            code_lines = []
            code_language = None

    def next_equation_id() -> str:
        nonlocal equation_index
        equation_index += 1
        return f"eq_{equation_index:04d}"

    index = 0
    while index < len(lines):
        raw_line = lines[index]
        line = raw_line.strip()
        if line.startswith("```"):
            if in_code_block:
                flush_code()
                in_code_block = False
            else:
                flush_paragraph()
                in_code_block = True
                info = line[3:].strip()
                code_language = info or None
            index += 1
            continue
        if in_code_block:
            code_lines.append(raw_line.rstrip())
            index += 1
            continue
        if not line or line == "---":
            flush_paragraph()
            index += 1
            continue
        if line == "$$":
            flush_paragraph()
            equation_lines: list[str] = []
            index += 1
            while index < len(lines) and lines[index].strip() != "$$":
                equation_lines.append(lines[index].rstrip())
                index += 1
            if index >= len(lines):
                paragraph_lines.append("$$")
                paragraph_lines.extend(equation_lines)
                break
            blocks.append(
                {
                    "kind": "equation",
                    "latex": "\n".join(equation_lines).strip(),
                    "id": next_equation_id(),
                }
            )
            index += 1
            continue
        if line.startswith("$$") and line.endswith("$$") and len(line) > 4:
            flush_paragraph()
            blocks.append(
                {
                    "kind": "equation",
                    "latex": line[2:-2].strip(),
                    "id": next_equation_id(),
                }
            )
            index += 1
            continue
        table_block = parse_simple_table(lines, index)
        if table_block is not None:
            flush_paragraph()
            rows, consumed = table_block
            blocks.append({"kind": "table", "rows": rows})
            index += consumed
            continue
        image_block = parse_image_block(line)
        if image_block is not None:
            flush_paragraph()
            blocks.append(image_block)
            index += 1
            continue
        if line.startswith("#"):
            flush_paragraph()
            marker, _, text = line.partition(" ")
            if text:
                blocks.append(
                    {
                        "kind": "heading",
                        "level": min(len(marker), 4),
                        "text": text.strip(),
                    }
                )
                index += 1
                continue
        list_item = parse_list_item(raw_line)
        if list_item is not None:
            flush_paragraph()
            blocks.append(list_item)
            index += 1
            continue
        paragraph_lines.append(line)
        index += 1

    flush_paragraph()
    flush_code()
    return blocks
