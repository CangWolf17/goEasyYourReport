from __future__ import annotations

import json
import re
from pathlib import Path

from scripts._docx_semantics import is_reference_section_title


def bibliography_label(index: int) -> str:
    return f"[{index}]"


def _is_bibliography_heading(block: dict[str, object]) -> bool:
    if block.get("kind") != "heading":
        return False
    return is_reference_section_title(str(block.get("text", "")))


def _entry_text(block: dict[str, object]) -> str | None:
    if block.get("kind") not in {"paragraph", "list_item"}:
        return None
    text = str(block.get("text", "")).strip()
    return text or None


def normalize_bibliography_entries(
    markdown_blocks: list[dict[str, object]],
) -> list[dict[str, object]]:
    entries: list[dict[str, object]] = []
    in_bibliography = False

    for block in markdown_blocks:
        if _is_bibliography_heading(block):
            in_bibliography = True
            continue
        if block.get("kind") == "heading":
            if in_bibliography:
                break
            continue
        if not in_bibliography:
            continue

        text = _entry_text(block)
        if not text:
            continue

        ordinal = len(entries) + 1
        label = bibliography_label(ordinal)
        entry_id = f"ref_{ordinal:04d}"
        entries.append(
            {
                "id": entry_id,
                "bookmark": entry_id,
                "ordinal": ordinal,
                "visible_label": label,
                "text": text,
                "rendered_text": f"{label} {text}",
            }
        )

    return entries


def should_emit_bibliography(plan: dict[str, object]) -> bool:
    semantics = plan.get("semantics", {})
    if not isinstance(semantics, dict):
        return False
    bibliography = semantics.get("bibliography", {})
    if not isinstance(bibliography, dict):
        return False
    return bool(bibliography.get("output_block_present", False))


def _plan_bibliography_settings(plan: dict[str, object]) -> dict[str, object]:
    semantics = plan.get("semantics", {})
    if not isinstance(semantics, dict):
        return {}
    bibliography = semantics.get("bibliography", {})
    return bibliography if isinstance(bibliography, dict) else {}


def _normalize_source_entry(
    entry: dict[str, object], ordinal: int
) -> dict[str, object] | None:
    title = str(entry.get("title", "")).strip()
    authors_raw = entry.get("authors", [])
    authors = [str(author).strip() for author in authors_raw if str(author).strip()]
    year = str(entry.get("year", "")).strip()
    doi = str(entry.get("doi", "")).strip()
    url = str(entry.get("url", "")).strip()
    if not title or not authors or not year or not (doi or url):
        return None

    entry_id = str(entry.get("id") or f"ref_{ordinal:04d}")
    label = bibliography_label(ordinal)
    container = str(entry.get("container", "")).strip()
    locator = f"doi:{doi}" if doi else url
    rendered_parts = [
        ", ".join(authors),
        title,
    ]
    if container:
        rendered_parts.append(container)
    rendered_parts.append(year)
    rendered_parts.append(locator)
    rendered_text = f"{label} " + ". ".join(part for part in rendered_parts if part)

    return {
        "id": entry_id,
        "bookmark": entry_id,
        "ordinal": ordinal,
        "visible_label": label,
        "title": title,
        "authors": authors,
        "year": year,
        "container": container,
        "doi": doi or None,
        "url": url or None,
        "rendered_text": rendered_text,
    }


def _load_json_source(path: Path) -> list[dict[str, object]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        entries = payload.get("entries")
        if isinstance(entries, list):
            return [item for item in entries if isinstance(item, dict)]
        return [payload]
    return []


def _load_bib_source(path: Path) -> list[dict[str, object]]:
    text = path.read_text(encoding="utf-8")
    entries: list[dict[str, object]] = []
    for match in re.finditer(r"@\w+\{[^,]+,(?P<body>.*?)\n\}", text, re.S):
        body = match.group("body")
        fields = dict(
            (field.lower(), value.strip().strip("{}"))
            for field, value in re.findall(r"(\w+)\s*=\s*\{([^}]*)\}", body)
        )
        authors = [item.strip() for item in fields.get("author", "").split(" and ") if item.strip()]
        entries.append(
            {
                "title": fields.get("title", ""),
                "authors": authors,
                "year": fields.get("year", ""),
                "container": fields.get("journal", "") or fields.get("booktitle", ""),
                "doi": fields.get("doi", ""),
                "url": fields.get("url", ""),
            }
        )
    return entries


def _load_ris_source(path: Path) -> list[dict[str, object]]:
    entries: list[dict[str, object]] = []
    current: dict[str, object] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if len(line) < 6 or line[2:6] != "  - ":
            continue
        tag = line[:2]
        value = line[6:].strip()
        if tag == "TY":
            current = {"authors": []}
            continue
        if tag == "ER":
            entries.append(current)
            current = {}
            continue
        if tag == "AU":
            current.setdefault("authors", []).append(value)
        elif tag == "TI":
            current["title"] = value
        elif tag == "PY":
            current["year"] = value[:4]
        elif tag in {"JO", "T2"}:
            current["container"] = value
        elif tag == "DO":
            current["doi"] = value
        elif tag == "UR":
            current["url"] = value
    return [entry for entry in entries if entry]


def load_bibliography_entries(
    project_root: Path | str, plan: dict[str, object]
) -> list[dict[str, object]]:
    settings = _plan_bibliography_settings(plan)
    source_mode = str(settings.get("source_mode", "needs_confirmation"))
    project_root = Path(project_root)

    raw_entries: list[dict[str, object]] = []
    if source_mode in {
        "agent_generate_verified_only",
        "agent_search_and_screen",
    }:
        evidence_path = project_root / str(
            settings.get("evidence_file", "./logs/bibliography.sources.json")
        ).replace("./", "")
        if evidence_path.exists():
            raw_entries.extend(_load_json_source(evidence_path))
    elif source_mode == "user_supplied_files":
        source_dir = project_root / str(
            settings.get("user_source_dir", "./docs/references")
        ).replace("./", "")
        if source_dir.exists():
            for path in sorted(source_dir.iterdir()):
                suffix = path.suffix.lower()
                if suffix == ".json":
                    raw_entries.extend(_load_json_source(path))
                elif suffix == ".bib":
                    raw_entries.extend(_load_bib_source(path))
                elif suffix == ".ris":
                    raw_entries.extend(_load_ris_source(path))

    entries: list[dict[str, object]] = []
    for raw_entry in raw_entries:
        normalized = _normalize_source_entry(raw_entry, len(entries) + 1)
        if normalized is not None:
            entries.append(normalized)
    return entries
