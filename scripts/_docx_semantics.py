from __future__ import annotations

import importlib
import re


REFERENCE_SECTION_TITLES = {"参考文献", "references"}
TOC_PLACEHOLDER_TEXTS = {"目录", "contents"}
REQUIRED_SEMANTIC_STYLES = [
    "题目",
    "标题2",
    "标题3",
    "标题4",
    "正文",
    "图题",
    "表题",
    "参考文献",
    "列表编号",
    "列表符号",
]
OUTLINE_LEVELS = {"标题2": 0, "标题3": 1, "标题4": 2}


def default_semantics() -> dict[str, object]:
    return {
        "style_policy": {
            "source_priority": [
                "task_book",
                "target_template",
                "repo_default",
            ],
            "title_style": "题目",
            "heading_styles": {
                "1": "标题2",
                "2": "标题3",
                "3": "标题4",
            },
            "outline_levels": OUTLINE_LEVELS.copy(),
            "body_style": "正文",
            "figure_caption_style": "图题",
            "table_caption_style": "表题",
            "reference_style": "参考文献",
            "list_styles": {
                "ordered": "列表编号",
                "unordered": "列表符号",
            },
            "table_defaults": {
                "first_row_top_border": True,
                "first_row_bottom_border": True,
                "last_row_bottom_border": True,
                "bold_first_column_when_row_header": True,
            },
        },
        "template_scan": {
            "style_candidates": {},
            "style_gaps": [],
            "outline_semantics_complete": False,
            "reference_block_present": False,
            "toc_signal": {
                "detected": False,
                "kind": "none",
            },
        },
        "toc": {
            "detected": False,
            "enabled": False,
            "needs_confirmation": False,
            "source": "none",
        },
        "cross_references": {
            "mode": "postprocess",
            "figure_table_enabled": "needs_confirmation",
            "equation_enabled": True,
            "bibliography_enabled": True,
            "style_mode": "body_text",
        },
        "equations": {
            "inline_enabled": True,
            "block_numbering": "parenthesized_global",
            "cross_reference_label": "公式({n})",
        },
        "bibliography": {
            "source_mode": "needs_confirmation",
            "output_block_present": False,
            "evidence_file": "./logs/bibliography.sources.json",
            "user_source_dir": "./docs/references",
        },
        "integrity": {
            "enabled": True,
            "last_result": None,
        },
    }


def ensure_plan_semantics(plan: dict[str, object]) -> dict[str, object]:
    semantics = plan.get("semantics")
    if not isinstance(semantics, dict):
        semantics = {}
        plan["semantics"] = semantics
    defaults = default_semantics()
    for key, value in defaults.items():
        current = semantics.get(key)
        if not isinstance(value, dict):
            semantics.setdefault(key, value)
            continue
        if not isinstance(current, dict):
            semantics[key] = value.copy()
            continue
        merged = value.copy()
        merged.update(current)
        semantics[key] = merged
    return semantics


def normalize_section_heading(text: str) -> str:
    normalized = text.strip()
    normalized = re.sub(r"^\s*[一二三四五六七八九十]+\s*[、.]?\s*", "", normalized)
    normalized = re.sub(r"^\s*\d+(?:\s*\.\s*\d+)*(?:[.)、])?\s*", "", normalized)
    normalized = re.sub(r"[:：]\s*$", "", normalized)
    return normalized.strip().lower()


def strip_section_prefix(text: str) -> str:
    return normalize_section_heading(text)


def is_reference_section_title(text: str) -> bool:
    return normalize_section_heading(text) in REFERENCE_SECTION_TITLES


def paragraph_has_toc_field(paragraph) -> bool:
    xml = paragraph._p.xml
    return 'instr="TOC' in xml or " TOC " in xml


def is_toc_placeholder_paragraph(paragraph) -> bool:
    text = paragraph.text.strip().lower()
    style_name = (
        paragraph.style.name.lower()
        if getattr(paragraph, "style", None) is not None
        else ""
    )
    return text in TOC_PLACEHOLDER_TEXTS or "toc" in style_name


def style_outline_level(style) -> int | None:
    if style is None or getattr(style, "element", None) is None:
        return None
    p_pr = style.element.find("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}pPr")
    if p_pr is None:
        return None
    outline = p_pr.find(
        "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}outlineLvl"
    )
    if outline is None:
        return None
    raw = outline.get("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}val")
    return None if raw is None else int(raw)


def detect_toc_signal(paragraphs: list[object]) -> dict[str, object]:
    for paragraph in paragraphs:
        if is_toc_placeholder_paragraph(paragraph):
            return {"detected": True, "kind": "placeholder"}
        if paragraph_has_toc_field(paragraph):
            return {"detected": True, "kind": "field"}
    return {"detected": False, "kind": "none"}


def detect_reference_block_signal(paragraphs: list[object]) -> dict[str, object]:
    for paragraph in paragraphs:
        if is_reference_section_title(paragraph.text):
            return {"present": True}
    return {"present": False}


def collect_template_semantics(doc) -> dict[str, object]:
    available_styles = sorted(
        {style.name for style in doc.styles if getattr(style, "name", None)}
    )
    style_set = set(available_styles)

    style_candidates = {
        "title": [name for name in ("题目", "Title") if name in style_set],
        "heading": [
            name
            for name in ("标题2", "标题3", "标题4", "Heading 1", "Heading 2", "Heading 3")
            if name in style_set
        ],
        "body": [name for name in ("正文", "Normal", "Body Text") if name in style_set],
        "list": [
            name
            for name in ("列表编号", "列表符号", "List Number", "List Bullet")
            if name in style_set
        ],
        "caption": [name for name in ("图题", "表题", "Caption") if name in style_set],
        "bibliography": [
            name for name in ("参考文献", "Body Text", "Normal") if name in style_set
        ],
    }
    style_gaps = [name for name in REQUIRED_SEMANTIC_STYLES if name not in style_set]

    outline_complete = True
    for style_name, expected_level in OUTLINE_LEVELS.items():
        if style_name not in style_set:
            outline_complete = False
            break
        if style_outline_level(doc.styles[style_name]) != expected_level:
            outline_complete = False
            break
    if "题目" in style_set and style_outline_level(doc.styles["题目"]) is not None:
        outline_complete = False

    toc_signal = detect_toc_signal(list(doc.paragraphs))
    reference_block = detect_reference_block_signal(list(doc.paragraphs))
    return {
        "available_styles": available_styles,
        "style_candidates": style_candidates,
        "style_gaps": style_gaps,
        "outline_semantics_complete": outline_complete,
        "toc_signal": toc_signal,
        "reference_block": reference_block,
        "outline": {
            "title_in_outline": "题目" in style_set
            and style_outline_level(doc.styles["题目"]) is not None,
            "mapped_levels": OUTLINE_LEVELS.copy(),
            "complete": outline_complete,
        },
    }


def should_bold_first_column(rows: list[list[str]]) -> bool:
    if len(rows) < 2:
        return False
    first_column = [row[0].strip() for row in rows[1:] if row]
    if not first_column:
        return False
    return all(value and not any(char.isdigit() for char in value) for value in first_column)


def apply_default_table_rules(
    table, *, template_overrides: dict[str, object] | None = None
) -> None:
    del template_overrides

    xml_module = importlib.import_module("docx.oxml")
    ns_module = importlib.import_module("docx.oxml.ns")

    tbl_pr = table._tbl.tblPr
    tbl_style = tbl_pr.find(ns_module.qn("w:tblStyle"))
    if tbl_style is not None:
        tbl_pr.remove(tbl_style)

    tbl_borders = tbl_pr.find(ns_module.qn("w:tblBorders"))
    if tbl_borders is None:
        tbl_borders = xml_module.OxmlElement("w:tblBorders")
        tbl_pr.append(tbl_borders)

    def set_table_border(edge: str, value: str) -> None:
        element = tbl_borders.find(ns_module.qn(f"w:{edge}"))
        if element is None:
            element = xml_module.OxmlElement(f"w:{edge}")
            tbl_borders.append(element)
        element.set(ns_module.qn("w:val"), value)

    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        set_table_border(edge, "nil")

    def set_border(cell, edge: str, enabled: bool) -> None:
        tc_pr = cell._tc.get_or_add_tcPr()
        borders = tc_pr.find(
            "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}tcBorders"
        )
        if borders is None:
            borders = xml_module.OxmlElement("w:tcBorders")
            tc_pr.append(borders)
        element = borders.find(
            f"{{http://schemas.openxmlformats.org/wordprocessingml/2006/main}}{edge}"
        )
        if not enabled:
            if element is not None:
                borders.remove(element)
            return
        if element is None:
            element = xml_module.OxmlElement(f"w:{edge}")
            borders.append(element)
        element.set(
            "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}val",
            "single",
        )
        element.set(
            "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}sz",
            "4",
        )
        element.set(
            "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}color",
            "000000",
        )

    for row_index, row in enumerate(table.rows):
        top_enabled = row_index == 0
        bottom_enabled = row_index == 0 or row_index == len(table.rows) - 1
        for cell in row.cells:
            set_border(cell, "top", top_enabled)
            set_border(cell, "bottom", bottom_enabled)
    return None
