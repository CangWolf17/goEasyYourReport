from __future__ import annotations

from copy import deepcopy
import importlib
import json
import re
from pathlib import Path

from scripts._docx_fields import add_bookmark, append_complex_field
from scripts._equation_omml import (
    UnsupportedEquationSyntax,
    latex_to_omml,
    numbered_latex_to_omml,
)
from scripts._docx_styles import (
    apply_paragraph_font_settings,
    apply_run_font_settings,
    body_style_name,
    figure_caption_style_name,
    preferred_heading_style,
    reference_style_name,
    style_font_settings,
    table_caption_style_name,
    title_style_name,
)
from scripts._report_markdown import cross_reference_placeholder_text
from scripts._docx_semantics import (
    apply_default_table_rules,
    is_reference_section_title,
    should_bold_first_column,
)
from scripts._docx_xml import (
    clear_paragraph,
    create_word_element,
    insert_paragraph_after,
    insert_paragraph_before,
    set_paragraph_pagination,
    word_qn,
)
from scripts._shared import load_json, project_path


SUPPORTED_CODE_LANGUAGES = {
    "python",
    "json",
    "bash",
    "yaml",
    "sql",
    "javascript",
    "typescript",
    "c",
    "cpp",
    "java",
}

CODE_LANGUAGE_ALIASES = {
    "py": "python",
    "sh": "bash",
    "shell": "bash",
    "yml": "yaml",
    "js": "javascript",
    "ts": "typescript",
    "c++": "cpp",
    "cc": "cpp",
    "cxx": "cpp",
}

BUILTIN_CODE_THEMES = {
    "github-light": {
        "background": "FFFFFF",
        "header_bg": "F6F8FA",
        "header_fg": "24292F",
        "border": "D0D7DE",
        "default": "24292F",
        "keyword": "CF222E",
        "string": "0A3069",
        "comment": "6E7781",
        "number": "0550AE",
        "function": "8250DF",
        "type": "953800",
        "operator": "24292F",
    }
}

SECTION_NUMBER_PREFIX_RE = re.compile(r"^\s*\d+(?:\s*\.\s*\d+)*(?:[.)、])?\s+")


def apply_named_style(paragraph, style_name: str | None) -> None:
    if style_name:
        paragraph.style = style_name


def normalize_hex_color(value: str) -> str:
    return value.strip().lstrip("#").upper()


def is_valid_hex_color(value: str) -> bool:
    normalized = normalize_hex_color(value)
    return bool(re.fullmatch(r"[0-9A-F]{6}", normalized))


def normalize_code_language(language: str | None) -> str | None:
    if not language:
        return None
    primary = language.strip().split()[0].lower()
    if not primary:
        return None
    return CODE_LANGUAGE_ALIASES.get(primary, primary)


def load_code_block_theme(project_root: Path | str) -> dict[str, object]:
    workflow_path = project_path(project_root, "workflow.json")
    theme_name = "github-light"
    override_path_value = "./config/code-theme.user.json"
    if workflow_path.exists():
        workflow = load_json(workflow_path)
        code_block_config = workflow.get("rendering", {}).get("code_blocks", {})
        theme_name = code_block_config.get("theme", theme_name)
        override_path_value = code_block_config.get(
            "theme_override", override_path_value
        )
    if theme_name not in BUILTIN_CODE_THEMES:
        theme_name = "github-light"
    roles = dict(BUILTIN_CODE_THEMES[theme_name])
    warnings: list[str] = []
    override_used = False

    override_path = project_path(
        project_root, str(override_path_value).replace("./", "")
    )
    if override_path.exists():
        try:
            override_payload = load_json(override_path)
            if not isinstance(override_payload, dict):
                raise ValueError("override payload must be an object")
            override_roles = override_payload.get("roles", {})
            if not isinstance(override_roles, dict):
                raise ValueError("roles must be an object")
            applied_override = False
            for role, color in override_roles.items():
                if role not in roles or not isinstance(color, str) or not color.strip():
                    continue
                if not is_valid_hex_color(color):
                    warnings.append(f"invalid code theme color for {role}: {color}")
                    continue
                roles[role] = normalize_hex_color(color)
                applied_override = True
            override_used = applied_override
        except (json.JSONDecodeError, ValueError, TypeError) as exc:
            warnings.append(f"invalid code theme override: {exc}")

    return {
        "name": theme_name,
        "override_used": override_used,
        "warnings": warnings,
        "roles": roles,
    }

def content_width(doc):
    section = doc.sections[0]
    return section.page_width - section.left_margin - section.right_margin


def set_cell_fill(cell, color: str) -> None:
    xml_module = importlib.import_module("docx.oxml")
    ns_module = importlib.import_module("docx.oxml.ns")
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = tc_pr.find(ns_module.qn("w:shd"))
    if shd is None:
        shd = xml_module.OxmlElement("w:shd")
        tc_pr.append(shd)
    shd.set(ns_module.qn("w:fill"), normalize_hex_color(color))


def set_paragraph_fill(paragraph, color: str) -> None:
    xml_module = importlib.import_module("docx.oxml")
    ns_module = importlib.import_module("docx.oxml.ns")
    p_pr = paragraph._p.get_or_add_pPr()
    shd = p_pr.find(ns_module.qn("w:shd"))
    if shd is None:
        shd = xml_module.OxmlElement("w:shd")
        p_pr.append(shd)
    shd.set(ns_module.qn("w:fill"), normalize_hex_color(color))


def set_cell_border(cell, color: str) -> None:
    xml_module = importlib.import_module("docx.oxml")
    ns_module = importlib.import_module("docx.oxml.ns")
    tc_pr = cell._tc.get_or_add_tcPr()
    borders = tc_pr.find(ns_module.qn("w:tcBorders"))
    if borders is None:
        borders = xml_module.OxmlElement("w:tcBorders")
        tc_pr.append(borders)
    for edge in ("top", "left", "bottom", "right"):
        element = borders.find(ns_module.qn(f"w:{edge}"))
        if element is None:
            element = xml_module.OxmlElement(f"w:{edge}")
            borders.append(element)
        element.set(ns_module.qn("w:val"), "single")
        element.set(ns_module.qn("w:sz"), "4")
        element.set(ns_module.qn("w:color"), normalize_hex_color(color))


def format_table_cell_paragraph(paragraph) -> None:
    shared_module = importlib.import_module("docx.shared")
    Pt = shared_module.Pt
    paragraph.paragraph_format.first_line_indent = Pt(0)
    paragraph.paragraph_format.line_spacing = 1.5
    paragraph.alignment = importlib.import_module(
        "docx.enum.text"
    ).WD_ALIGN_PARAGRAPH.CENTER


def format_reference_entry_paragraph(
    paragraph, body_font: dict[str, str] | None
) -> None:
    shared_module = importlib.import_module("docx.shared")
    Pt = shared_module.Pt
    paragraph.paragraph_format.left_indent = Pt(0)
    paragraph.paragraph_format.first_line_indent = Pt(0)
    paragraph.paragraph_format.line_spacing = 1.5
    reference_font = dict(body_font or {})
    reference_font["size"] = "21"
    apply_paragraph_font_settings(paragraph, reference_font)


def table_cell_font_settings() -> dict[str, str]:
    return {
        "ascii": "宋体",
        "hAnsi": "宋体",
        "eastAsia": "宋体",
        "size": "21",
    }


def convert_inline_picture_to_top_bottom_anchor(run) -> None:
    xml_module = importlib.import_module("docx.oxml")
    ns_module = importlib.import_module("docx.oxml.ns")
    drawing = run._r.find(ns_module.qn("w:drawing"))
    if drawing is None:
        return
    inline = drawing.find(ns_module.qn("wp:inline"))
    if inline is None:
        return

    anchor = xml_module.OxmlElement("wp:anchor")
    for key, value in {
        "distT": "0",
        "distB": "0",
        "distL": "0",
        "distR": "0",
        "simplePos": "0",
        "relativeHeight": "251659264",
        "behindDoc": "0",
        "locked": "0",
        "layoutInCell": "1",
        "allowOverlap": "1",
    }.items():
        anchor.set(key, value)

    simple_pos = xml_module.OxmlElement("wp:simplePos")
    simple_pos.set("x", "0")
    simple_pos.set("y", "0")

    position_h = xml_module.OxmlElement("wp:positionH")
    position_h.set("relativeFrom", "margin")
    align_h = xml_module.OxmlElement("wp:align")
    align_h.text = "center"
    position_h.append(align_h)

    position_v = xml_module.OxmlElement("wp:positionV")
    position_v.set("relativeFrom", "paragraph")
    pos_offset = xml_module.OxmlElement("wp:posOffset")
    pos_offset.text = "0"
    position_v.append(pos_offset)

    wrap = xml_module.OxmlElement("wp:wrapTopAndBottom")

    anchor.append(simple_pos)
    anchor.append(position_h)
    anchor.append(position_v)

    for child_name in (
        "wp:extent",
        "wp:effectExtent",
        "wp:docPr",
        "wp:cNvGraphicFramePr",
        "a:graphic",
    ):
        child = inline.find(ns_module.qn(child_name))
        if child is not None:
            if child_name == "wp:effectExtent":
                anchor.append(deepcopy(child))
            elif child_name == "wp:docPr":
                anchor.append(wrap)
                anchor.append(deepcopy(child))
            else:
                anchor.append(deepcopy(child))

    if wrap.getparent() is None:
        anchor.insert(4, wrap)

    drawing.remove(inline)
    drawing.append(anchor)


def style_code_run(run, color: str) -> None:
    shared_module = importlib.import_module("docx.shared")
    Pt = shared_module.Pt
    RGBColor = shared_module.RGBColor
    run.font.name = "Consolas"
    run.font.size = Pt(10)
    run.font.color.rgb = RGBColor.from_string(normalize_hex_color(color))


def code_role_for_token(token_type, token_root) -> str:
    if token_type in token_root.Comment:
        return "comment"
    if token_type in token_root.Keyword:
        return "keyword"
    if token_type in token_root.Literal.String:
        return "string"
    if token_type in token_root.Literal.Number:
        return "number"
    if token_type in token_root.Name.Function:
        return "function"
    if token_type in token_root.Name.Class or token_type in token_root.Keyword.Type:
        return "type"
    if token_type in token_root.Operator:
        return "operator"
    return "default"


def add_code_body_paragraph(cell):
    shared_module = importlib.import_module("docx.shared")
    Pt = shared_module.Pt
    paragraph = cell.add_paragraph()
    paragraph.paragraph_format.space_before = Pt(0)
    paragraph.paragraph_format.space_after = Pt(0)
    return paragraph


def render_plain_code_lines(cell, code_text: str, roles: dict[str, str]) -> None:
    lines = code_text.splitlines() or [""]
    for line in lines:
        paragraph = add_code_body_paragraph(cell)
        run = paragraph.add_run(line)
        style_code_run(run, roles["default"])


def render_highlighted_code_lines(
    cell,
    code_text: str,
    normalized_language: str,
    roles: dict[str, str],
) -> bool:
    pygments_module = importlib.import_module("pygments")
    lexers_module = importlib.import_module("pygments.lexers")
    token_module = importlib.import_module("pygments.token")
    util_module = importlib.import_module("pygments.util")

    try:
        lexer = lexers_module.get_lexer_by_name(normalized_language)
    except util_module.ClassNotFound:
        render_plain_code_lines(cell, code_text, roles)
        return False

    paragraph = add_code_body_paragraph(cell)
    wrote_any = False
    for token_type, value in pygments_module.lex(code_text, lexer):
        chunks = value.split("\n")
        for index, chunk in enumerate(chunks):
            if chunk:
                role = code_role_for_token(token_type, token_module.Token)
                run = paragraph.add_run(chunk)
                style_code_run(run, roles.get(role, roles["default"]))
                wrote_any = True
            if index < len(chunks) - 1:
                paragraph = add_code_body_paragraph(cell)
    if not wrote_any:
        run = paragraph.add_run("")
        style_code_run(run, roles["default"])
    return True


def insert_code_table_after(
    block,
    code_text: str,
    width,
    language: str | None = None,
    code_theme: dict[str, object] | None = None,
    code_status: dict[str, object] | None = None,
):
    shared_module = importlib.import_module("docx.shared")
    color_module = importlib.import_module("docx.shared")
    Pt = shared_module.Pt
    RGBColor = color_module.RGBColor
    roles = (code_theme or load_code_block_theme("."))["roles"]
    if hasattr(block, "_p"):
        parent = block._parent
        anchor = block._p
    else:
        parent = block._parent
        anchor = block._tbl
    table = parent.add_table(rows=1, cols=1, width=width)
    anchor.addnext(table._tbl)

    cell = table.cell(0, 0)
    set_cell_fill(cell, roles["background"])
    set_cell_border(cell, roles["border"])

    normalized_language = normalize_code_language(language)
    header_label = normalized_language or "Code"

    header = cell.paragraphs[0]
    header.paragraph_format.space_before = Pt(0)
    header.paragraph_format.space_after = Pt(3)
    set_paragraph_fill(header, roles["header_bg"])
    header_run = header.add_run(header_label)
    header_run.bold = True
    header_run.font.size = Pt(9)
    header_run.font.color.rgb = RGBColor.from_string(
        normalize_hex_color(roles["header_fg"])
    )

    highlighted = False
    if code_status is not None:
        code_status["styled"] += 1
    if normalized_language in SUPPORTED_CODE_LANGUAGES:
        highlighted = render_highlighted_code_lines(
            cell, code_text, normalized_language, roles
        )
        if highlighted and code_status is not None:
            code_status["highlighted"] += 1
    else:
        render_plain_code_lines(cell, code_text, roles)
        if language and code_status is not None:
            code_status["unsupported"].append(
                {
                    "language": str(language).strip().split()[0].lower(),
                    "normalized": None,
                    "action": "agent_handoff_required",
                }
            )
    return table


def insert_markdown_table_after(block, rows: list[list[str]], width):
    if hasattr(block, "_p"):
        parent = block._parent
        anchor = block._p
    else:
        parent = block._parent
        anchor = block._tbl

    column_count = max((len(row) for row in rows), default=1)
    table = parent.add_table(rows=len(rows), cols=column_count, width=width)
    anchor.addnext(table._tbl)

    table_module = importlib.import_module("docx.enum.table")
    table.alignment = table_module.WD_TABLE_ALIGNMENT.CENTER

    for row_index, row_values in enumerate(rows):
        for col_index, value in enumerate(row_values):
            cell = table.cell(row_index, col_index)
            cell.vertical_alignment = table_module.WD_CELL_VERTICAL_ALIGNMENT.CENTER
            cell.text = value
            for paragraph in cell.paragraphs:
                format_table_cell_paragraph(paragraph)
                apply_paragraph_font_settings(paragraph, table_cell_font_settings())
            if row_index == 0:
                for paragraph in cell.paragraphs:
                    for run in paragraph.runs:
                        run.bold = True
    apply_default_table_rules(table)
    if should_bold_first_column(rows):
        for row_index in range(1, len(rows)):
            cell = table.cell(row_index, 0)
            for paragraph in cell.paragraphs:
                for run in paragraph.runs:
                    run.bold = True
    return table


def make_caption(prefix: str, index: int, label: str | None = None) -> str:
    suffix = f" {label.strip()}" if label and label.strip() else ""
    return f"{prefix}{index}{suffix}"


def apply_caption_field(
    paragraph,
    *,
    style_name: str | None,
    prefix: str,
    sequence_name: str,
    ordinal: int,
    bookmark_name: str,
    label: str | None = None,
) -> None:
    clear_paragraph(paragraph)
    apply_named_style(paragraph, style_name)
    set_paragraph_pagination(paragraph, keep_next=True, keep_lines=True)
    paragraph.add_run(prefix)
    append_complex_field(
        paragraph,
        f" SEQ {sequence_name} \\* ARABIC ",
        display_text=str(ordinal),
    )
    if label and label.strip():
        paragraph.add_run(f" {label.strip()}")
    add_bookmark(paragraph, bookmark_name)


def equation_ordinal(block: dict[str, object]) -> int:
    block_id = str(block.get("id", "eq_0001"))
    return int(block_id.split("_", 1)[1])


def record_unsupported_equation(
    equation_status: dict[str, object] | None, latex: str
) -> None:
    if equation_status is None:
        return
    equation_status.setdefault("unsupported", []).append(
        {
            "kind": "unsupported_equation_syntax",
            "severity": "handoff",
            "latex": latex,
        }
    )


def append_inline_equation(paragraph, latex: str, equation_status: dict[str, object] | None) -> None:
    try:
        paragraph._p.append(latex_to_omml(latex))
    except UnsupportedEquationSyntax:
        record_unsupported_equation(equation_status, latex)
        paragraph.add_run(f"${latex}$")


def apply_equation_block(
    paragraph,
    block: dict[str, object],
    available_styles: set[str],
    equation_status: dict[str, object] | None,
) -> None:
    clear_paragraph(paragraph)
    apply_named_style(paragraph, body_style_name(available_styles))
    paragraph.paragraph_format.first_line_indent = importlib.import_module(
        "docx.shared"
    ).Pt(0)
    set_paragraph_pagination(paragraph, keep_lines=True)
    bookmark_name = str(block.get("id", "eq_0001"))
    latex = str(block.get("latex", "")).strip()
    try:
        paragraph._p.append(numbered_latex_to_omml(latex, equation_ordinal(block)))
        add_bookmark(paragraph, bookmark_name)
    except UnsupportedEquationSyntax:
        record_unsupported_equation(equation_status, latex)
        paragraph.add_run(f"$${latex}$$")
        add_bookmark(paragraph, bookmark_name)


def caption_label_from_heading(text: str) -> str:
    stripped = text.strip()
    normalized = SECTION_NUMBER_PREFIX_RE.sub("", stripped, count=1).strip()
    return normalized or stripped


def fallback_list_text(block: dict[str, object]) -> str:
    text = str(block.get("text", "")).strip()
    depth = max(int(block.get("depth", 0)), 0)
    indent = "  " * depth
    if block.get("ordered"):
        number = int(block.get("number", 1) or 1)
        return f"{indent}{number}. {text}"
    return f"{indent}- {text}"


def apply_image_block(
    paragraph,
    block: dict[str, object],
    available_styles: set[str],
    width,
    body_dir: Path,
    image_status: dict[str, list[dict[str, str]]],
):
    clear_paragraph(paragraph)
    alt = str(block.get("alt", "Image"))
    raw_path = str(block.get("path", "")).strip()
    image_path = Path(raw_path)
    resolved_path = image_path if image_path.is_absolute() else body_dir / image_path
    details = {
        "alt": alt,
        "path": raw_path,
        "resolved_path": str(resolved_path),
    }

    if not resolved_path.exists():
        if "Caption" in available_styles:
            paragraph.style = "Caption"
        paragraph.add_run(f"[Image Insert Failed] {alt} ({raw_path}): file not found")
        image_status["failed"].append({**details, "reason": "file not found"})
        return paragraph, False

    try:
        paragraph.alignment = importlib.import_module(
            "docx.enum.text"
        ).WD_ALIGN_PARAGRAPH.CENTER
        set_paragraph_pagination(paragraph, keep_next=True, keep_lines=True)
        run = paragraph.add_run()
        run.add_picture(str(resolved_path), width=width)
        image_status["inserted"].append(details)
    except Exception as exc:
        if "Caption" in available_styles:
            paragraph.style = "Caption"
        paragraph.add_run(f"[Image Insert Failed] {alt} ({raw_path}): {exc}")
        image_status["failed"].append({**details, "reason": str(exc)})
        return paragraph, False
    return paragraph, True


def apply_block(
    paragraph,
    block: dict[str, object],
    available_styles: set[str],
    *,
    forced_style: str | None = None,
    equation_status: dict[str, object] | None = None,
) -> None:
    clear_paragraph(paragraph)
    body_font = style_font_settings(
        paragraph.part.document.styles, body_style_name(available_styles)
    )
    text = str(block.get("text", ""))
    segments = block.get("segments")
    render_segments = segments
    kind = block.get("kind")
    if forced_style is not None:
        apply_named_style(paragraph, forced_style)
    elif kind == "heading":
        level_raw = block.get("level", 1)
        level = int(level_raw) if isinstance(level_raw, (int, str)) else 1
        apply_named_style(paragraph, preferred_heading_style(level, available_styles))
    elif kind == "list_item":
        ordered = bool(block.get("ordered"))
        depth = int(block.get("depth", 0))
        base = "List Number" if ordered else "List Bullet"
        style_name = base if depth == 0 else f"{base} {depth + 1}"
        semantic_style = "列表编号" if ordered else "列表符号"
        text = str(block.get("text", ""))
        if semantic_style in available_styles:
            paragraph.style = semantic_style
        elif style_name in available_styles:
            paragraph.style = style_name
        elif "List Paragraph" in available_styles:
            paragraph.style = "List Paragraph"
            text = fallback_list_text(block)
            render_segments = None
        else:
            text = fallback_list_text(block)
            render_segments = None
    else:
        apply_named_style(paragraph, body_style_name(available_styles))
    if kind == "paragraph" and isinstance(render_segments, list):
        for segment in render_segments:
            if segment.get("kind") == "cross_reference":
                paragraph.add_run(cross_reference_placeholder_text(segment))
            elif segment.get("kind") == "inline_equation":
                append_inline_equation(
                    paragraph,
                    str(segment.get("latex", "")),
                    equation_status,
                )
            else:
                paragraph.add_run(str(segment.get("text", "")))
        apply_paragraph_font_settings(paragraph, body_font)
        return
    if kind == "list_item" and isinstance(render_segments, list):
        for segment in render_segments:
            if segment.get("kind") == "cross_reference":
                paragraph.add_run(cross_reference_placeholder_text(segment))
            elif segment.get("kind") == "inline_equation":
                append_inline_equation(
                    paragraph,
                    str(segment.get("latex", "")),
                    equation_status,
                )
            else:
                paragraph.add_run(str(segment.get("text", "")))
        apply_paragraph_font_settings(paragraph, body_font)
        return
    if kind == "equation":
        apply_equation_block(paragraph, block, available_styles, equation_status)
        return
    run = paragraph.add_run(text)
    if kind == "list_item":
        apply_run_font_settings(run, body_font)
    elif kind == "paragraph":
        apply_paragraph_font_settings(paragraph, body_font)


def render_blocks(
    doc,
    region: dict[str, object],
    blocks: list[dict[str, object]],
    body_dir: Path,
    code_theme: dict[str, object],
    code_status: dict[str, object],
    semantics: dict[str, object] | None = None,
    equation_status: dict[str, object] | None = None,
) -> dict[str, list[dict[str, str]]]:
    start_raw = region.get("start_paragraph")
    end_raw = region.get("end_paragraph")
    if not isinstance(start_raw, int) or start_raw >= len(doc.paragraphs):
        return {"inserted": [], "failed": []}
    start = start_raw
    end = end_raw if isinstance(end_raw, int) else None

    stop = min(end + 1, len(doc.paragraphs)) if end is not None else len(doc.paragraphs)
    original_region = doc.paragraphs[start:stop]
    if not original_region:
        return {"inserted": [], "failed": []}

    available_styles = {
        style.name for style in doc.styles if getattr(style, "name", None)
    }
    body_font = style_font_settings(doc.styles, body_style_name(available_styles))
    width = content_width(doc)
    image_status: dict[str, list[dict[str, str]]] = {"inserted": [], "failed": []}
    figure_index = 0
    table_index = 0
    last_heading_text = ""
    bibliography = (semantics or {}).get("bibliography", {})
    reference_output_enabled = bool(bibliography.get("output_block_present", False))
    in_reference_section = False
    first_block_is_title = bool(
        blocks
        and blocks[0].get("kind") == "heading"
        and int(blocks[0].get("level", 1)) == 1
    )

    def normalized_block(
        block: dict[str, object], block_index: int
    ) -> tuple[dict[str, object], str | None]:
        if block.get("kind") != "heading":
            return block, None
        level = int(block.get("level", 1))
        if block_index == 0 and first_block_is_title:
            return block, title_style_name(available_styles)
        if first_block_is_title and block_index > 0 and level > 1:
            return {**block, "level": level - 1}, None
        return block, None

    def paragraph_style_for_block(block: dict[str, object]) -> str | None:
        if (
            reference_output_enabled
            and in_reference_section
            and block.get("kind") in {"paragraph", "list_item"}
        ):
            return reference_style_name(available_styles)
        if block.get("kind") == "paragraph":
            return body_style_name(available_styles)
        return None

    current = original_region[0]
    if blocks:
        first_block, first_forced_style = normalized_block(blocks[0], 0)
        first_kind = first_block.get("kind")
        if first_kind == "code":
            clear_paragraph(current)
            used_last = insert_code_table_after(
                current,
                str(first_block.get("text", "")),
                width,
                str(first_block.get("language", "") or "") or None,
                code_theme,
                code_status,
            )
        elif first_kind == "table":
            rows = first_block.get("rows", [])
            if not isinstance(rows, list):
                rows = []
            table_index += 1
            apply_caption_field(
                current,
                style_name=table_caption_style_name(available_styles),
                prefix="表",
                sequence_name="表",
                ordinal=table_index,
                bookmark_name=f"tbl_{table_index:04d}",
                label=caption_label_from_heading(last_heading_text),
            )
            used_last = insert_markdown_table_after(current, rows, width)
        elif first_kind == "image":
            figure_index += 1
            image_paragraph, inserted = apply_image_block(
                current,
                first_block,
                available_styles,
                width,
                body_dir,
                image_status,
            )
            used_last = image_paragraph
            if inserted:
                caption = insert_paragraph_after(image_paragraph)
                apply_caption_field(
                    caption,
                    style_name=figure_caption_style_name(available_styles),
                    prefix="图",
                    sequence_name="图",
                    ordinal=figure_index,
                    bookmark_name=f"fig_{figure_index:04d}",
                    label=str(first_block.get("alt", "")).strip(),
                )
                used_last = caption
        elif first_kind == "equation":
            apply_block(
                current,
                first_block,
                available_styles,
                forced_style=first_forced_style
                or paragraph_style_for_block(first_block),
                equation_status=equation_status,
            )
            used_last = current
        else:
            apply_block(
                current,
                first_block,
                available_styles,
                forced_style=first_forced_style
                or paragraph_style_for_block(first_block),
                equation_status=equation_status,
            )
            used_last = current
        if (
            reference_output_enabled
            and in_reference_section
            and first_block.get("kind") in {"paragraph", "list_item"}
        ):
            format_reference_entry_paragraph(used_last, body_font)
        if first_kind == "heading":
            last_heading_text = str(first_block.get("text", "")).strip()
            in_reference_section = (
                reference_output_enabled
                and is_reference_section_title(last_heading_text)
            )
    else:
        clear_paragraph(current)
        used_last = current

    for block_index, block in enumerate(blocks[1:], start=1):
        block, forced_style = normalized_block(block, block_index)
        if block.get("kind") == "code":
            used_last = insert_code_table_after(
                used_last,
                str(block.get("text", "")),
                width,
                str(block.get("language", "") or "") or None,
                code_theme,
                code_status,
            )
        elif block.get("kind") == "table":
            table_index += 1
            caption = insert_paragraph_after(used_last)
            apply_caption_field(
                caption,
                style_name=table_caption_style_name(available_styles),
                prefix="表",
                sequence_name="表",
                ordinal=table_index,
                bookmark_name=f"tbl_{table_index:04d}",
                label=caption_label_from_heading(last_heading_text),
            )
            rows = block.get("rows", [])
            if not isinstance(rows, list):
                rows = []
            used_last = insert_markdown_table_after(caption, rows, width)
        elif block.get("kind") == "image":
            used_last = insert_paragraph_after(used_last)
            figure_index += 1
            image_paragraph, inserted = apply_image_block(
                used_last,
                block,
                available_styles,
                width,
                body_dir,
                image_status,
            )
            used_last = image_paragraph
            if inserted:
                caption = insert_paragraph_after(image_paragraph)
                apply_caption_field(
                    caption,
                    style_name=figure_caption_style_name(available_styles),
                    prefix="图",
                    sequence_name="图",
                    ordinal=figure_index,
                    bookmark_name=f"fig_{figure_index:04d}",
                    label=str(block.get("alt", "")).strip(),
                )
                used_last = caption
        elif block.get("kind") == "equation":
            used_last = insert_paragraph_after(used_last)
            apply_block(
                used_last,
                block,
                available_styles,
                forced_style=forced_style or paragraph_style_for_block(block),
                equation_status=equation_status,
            )
        else:
            used_last = insert_paragraph_after(used_last)
            apply_block(
                used_last,
                block,
                available_styles,
                forced_style=forced_style or paragraph_style_for_block(block),
                equation_status=equation_status,
            )
            if (
                reference_output_enabled
                and in_reference_section
                and block.get("kind") in {"paragraph", "list_item"}
            ):
                format_reference_entry_paragraph(used_last, body_font)
            if block.get("kind") == "heading":
                last_heading_text = str(block.get("text", "")).strip()
                in_reference_section = (
                    reference_output_enabled
                    and is_reference_section_title(last_heading_text)
                )

    for paragraph in original_region[1:]:
        if paragraph._element.getparent() is not None:
            paragraph._element.getparent().remove(paragraph._element)
    return image_status
