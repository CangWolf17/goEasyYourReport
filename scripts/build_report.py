from __future__ import annotations

import argparse
import importlib
import re
import shutil
import subprocess
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts._bibliography import load_bibliography_entries, should_emit_bibliography
from scripts._docx_integrity import validate_docx_package
from scripts._docx_fields import (
    add_bookmark,
    append_reference_hyperlink,
    insert_toc_field,
)
from scripts._docx_xml import (
    clear_paragraph,
    create_word_element,
    insert_paragraph_after,
    insert_paragraph_before,
    word_qn,
)
from scripts._report_markdown import (
    cross_reference_placeholder_text,
    markdown_to_blocks,
    parse_paragraph_segments,
)
from scripts._report_render import load_code_block_theme, render_blocks
from scripts._report_render import (
    apply_paragraph_font_settings,
    body_style_name,
    style_font_settings,
)
from scripts._shared import emit_json, import_docx, load_json, project_path


def paragraph_has_toc_field(paragraph) -> bool:
    xml = paragraph._p.xml
    return 'instr="TOC' in xml or " TOC " in xml


def is_toc_placeholder(paragraph) -> bool:
    text = paragraph.text.strip().lower()
    style_name = (
        paragraph.style.name.lower()
        if getattr(paragraph, "style", None) is not None
        else ""
    )
    return text in {"目录", "contents"} or "toc" in style_name


def find_toc_anchor(doc):
    for paragraph in doc.paragraphs:
        if paragraph_has_toc_field(paragraph):
            return paragraph
    for paragraph in doc.paragraphs:
        if is_toc_placeholder(paragraph):
            return paragraph
    return None


def ensure_style_rpr(style):
    r_pr = style.element.find(word_qn("w:rPr"))
    if r_pr is None:
        r_pr = create_word_element("w:rPr")
        style.element.append(r_pr)
    return r_pr


def ensure_style_ppr(style):
    p_pr = style.element.find(word_qn("w:pPr"))
    if p_pr is None:
        p_pr = create_word_element("w:pPr")
        style.element.append(p_pr)
    return p_pr


def find_style_by_id(styles, style_id: str):
    for style in styles:
        if getattr(style, "style_id", None) == style_id:
            return style
    return None


def apply_toc_style_formatting(style) -> None:
    enum_text = importlib.import_module("docx.enum.text")
    shared = importlib.import_module("docx.shared")
    Pt = shared.Pt

    style.font.name = "宋体"
    style.font.size = Pt(14)
    style.paragraph_format.alignment = enum_text.WD_ALIGN_PARAGRAPH.LEFT
    style.paragraph_format.line_spacing = 1.5
    style.paragraph_format.left_indent = Pt(0)
    style.paragraph_format.first_line_indent = Pt(0)

    p_pr = ensure_style_ppr(style)
    spacing = p_pr.find(word_qn("w:spacing"))
    if spacing is None:
        spacing = create_word_element("w:spacing")
        p_pr.append(spacing)
    spacing.set(word_qn("w:line"), "360")
    spacing.set(word_qn("w:lineRule"), "auto")

    ind = p_pr.find(word_qn("w:ind"))
    if ind is None:
        ind = create_word_element("w:ind")
        p_pr.append(ind)
    for attribute in (
        "w:left",
        "w:leftChars",
        "w:firstLine",
        "w:firstLineChars",
        "w:hanging",
        "w:hangingChars",
    ):
        ind.set(word_qn(attribute), "0")

    jc = p_pr.find(word_qn("w:jc"))
    if jc is None:
        jc = create_word_element("w:jc")
        p_pr.append(jc)
    jc.set(word_qn("w:val"), "left")

    r_pr = ensure_style_rpr(style)
    r_fonts = r_pr.find(word_qn("w:rFonts"))
    if r_fonts is None:
        r_fonts = create_word_element("w:rFonts")
        r_pr.append(r_fonts)
    for key in ("ascii", "hAnsi", "eastAsia"):
        r_fonts.set(word_qn(f"w:{key}"), "宋体")

    size = r_pr.find(word_qn("w:sz"))
    if size is None:
        size = create_word_element("w:sz")
        r_pr.append(size)
    size.set(word_qn("w:val"), "28")

    size_cs = r_pr.find(word_qn("w:szCs"))
    if size_cs is None:
        size_cs = create_word_element("w:szCs")
        r_pr.append(size_cs)
    size_cs.set(word_qn("w:val"), "28")


def ensure_toc_styles(doc) -> None:
    styles = doc.styles
    enum_style = importlib.import_module("docx.enum.style")

    for style_name in ("目录1", "目录2", "目录3"):
        try:
            style = styles[style_name]
        except KeyError:
            style = styles.add_style(style_name, enum_style.WD_STYLE_TYPE.PARAGRAPH)
        apply_toc_style_formatting(style)

    for style_id in ("TOC1", "TOC2", "TOC3"):
        style = find_style_by_id(styles, style_id)
        if style is not None:
            apply_toc_style_formatting(style)


def toc_title_style_name(doc) -> str | None:
    available_styles = {
        style.name for style in doc.styles if getattr(style, "name", None)
    }
    for candidate in ("题目", "Title"):
        if candidate in available_styles:
            return candidate
    return None


def refresh_toc_with_word_if_available(docx_path: Path) -> bool:
    if sys.platform != "win32":
        return False

    powershell = shutil.which("powershell") or shutil.which("powershell.exe")
    if not powershell:
        return False

    escaped = str(docx_path).replace("'", "''")
    script = (
        "$path = '{path}'; "
        "$word = $null; $doc = $null; "
        "try {{ "
        "$word = New-Object -ComObject Word.Application; "
        "$word.Visible = $false; "
        "$word.DisplayAlerts = 0; "
        "$doc = $word.Documents.Open($path, $false, $false); "
        "if ($doc.TablesOfContents.Count -gt 0) {{ "
        "for ($i = 1; $i -le $doc.TablesOfContents.Count; $i++) {{ "
        "$doc.TablesOfContents.Item($i).Update() "
        "}}; "
        "$doc.Save(); "
        "Write-Output 'updated' "
        "}} "
        "}} catch {{ "
        "Write-Output 'skipped' "
        "}} finally {{ "
        "if ($doc -ne $null) {{ $doc.Close() }}; "
        "if ($word -ne $null) {{ $word.Quit() }} "
        "}}"
    ).format(path=escaped)
    result = subprocess.run(
        [powershell, "-NoProfile", "-Command", script],
        capture_output=True,
        text=True,
        timeout=120,
    )
    return result.returncode == 0 and "updated" in result.stdout


def apply_toc_if_enabled(doc, plan: dict[str, object]) -> None:
    semantics = plan.get("semantics", {})
    if not isinstance(semantics, dict):
        return
    toc = semantics.get("toc", {})
    if not isinstance(toc, dict):
        return
    if not toc.get("enabled"):
        return

    ensure_toc_styles(doc)
    title_paragraph = find_toc_anchor(doc)
    field_paragraph = None
    if title_paragraph is None:
        fillable = plan.get("regions", {}).get("fillable", [])
        if not fillable:
            return
        start_paragraph = fillable[0].get("start_paragraph")
        if not isinstance(start_paragraph, int) or start_paragraph >= len(doc.paragraphs):
            return
        body_anchor = doc.paragraphs[start_paragraph]
        paragraph_type = importlib.import_module("docx.text.paragraph").Paragraph
        page_breaks_before_body = []
        previous_element = body_anchor._p.getprevious()
        while previous_element is not None and previous_element.tag == word_qn("w:p"):
            previous_paragraph = paragraph_type(previous_element, body_anchor._parent)
            if 'w:type="page"' not in previous_paragraph._p.xml:
                break
            page_breaks_before_body.insert(0, previous_paragraph)
            previous_element = previous_element.getprevious()

        if page_breaks_before_body:
            before_toc_break = page_breaks_before_body[0]
            title_paragraph = insert_paragraph_after(before_toc_break)
            field_paragraph = insert_paragraph_after(title_paragraph)
            if len(page_breaks_before_body) == 1:
                after_toc_break = insert_paragraph_after(field_paragraph)
                after_toc_break.add_run().add_break(
                    importlib.import_module("docx.enum.text").WD_BREAK.PAGE
                )
            else:
                after_toc_break = page_breaks_before_body[1]
                for extra_break in page_breaks_before_body[2:]:
                    parent = extra_break._element.getparent()
                    if parent is not None:
                        parent.remove(extra_break._element)
        else:
            field_paragraph = insert_paragraph_before(body_anchor)
            title_paragraph = insert_paragraph_before(field_paragraph)
            before_toc_break = insert_paragraph_before(title_paragraph)
            before_toc_break.add_run().add_break(
                importlib.import_module("docx.enum.text").WD_BREAK.PAGE
            )
            after_toc_break = insert_paragraph_after(field_paragraph)
            after_toc_break.add_run().add_break(
                importlib.import_module("docx.enum.text").WD_BREAK.PAGE
            )
    else:
        field_paragraph = insert_paragraph_after(title_paragraph)

    clear_paragraph(title_paragraph)
    title_style = toc_title_style_name(doc)
    if title_style:
        title_paragraph.style = title_style
    title_paragraph.add_run("目录")

    clear_paragraph(field_paragraph)
    insert_toc_field(field_paragraph, (1, 3), display_text="")


def reference_label(target_kind: str, target_id: str) -> str:
    ordinal = int(target_id.split("_", 1)[1])
    if target_kind == "figure":
        return f"图{ordinal}"
    if target_kind == "table":
        return f"表{ordinal}"
    if target_kind == "equation":
        return f"公式({ordinal})"
    if target_kind == "bibliography":
        return f"[{ordinal}]"
    raise ValueError(f"Unsupported reference kind: {target_kind}")


def strip_section_prefix(text: str) -> str:
    normalized = re.sub(r"^\s*[一二三四五六七八九十]+\s*[、.]?\s*", "", text.strip())
    normalized = re.sub(r"^\s*\d+(?:\.\d+)*\s*", "", normalized)
    normalized = re.sub(r"[:：]\s*$", "", normalized)
    return normalized.strip().lower()


def build_reference_registry(doc) -> dict[str, dict[str, dict[str, str]]]:
    registry: dict[str, dict[str, dict[str, str]]] = {
        "figure": {},
        "table": {},
        "equation": {},
        "bibliography": {},
    }
    for paragraph in doc.paragraphs:
        for element in paragraph._p.iter(word_qn("w:bookmarkStart")):
            bookmark_name = element.get(word_qn("w:name"))
            if not bookmark_name:
                continue
            if bookmark_name.startswith("fig_"):
                target_kind = "figure"
            elif bookmark_name.startswith("tbl_"):
                target_kind = "table"
            elif bookmark_name.startswith("eq_"):
                target_kind = "equation"
            elif bookmark_name.startswith("ref_"):
                target_kind = "bibliography"
            else:
                continue
            registry[target_kind][bookmark_name] = {
                "bookmark": bookmark_name,
                "label": reference_label(target_kind, bookmark_name),
            }
    return registry


def apply_cross_reference_pass(doc, plan: dict[str, object]) -> None:
    semantics = plan.get("semantics", {})
    if not isinstance(semantics, dict):
        return
    cross_references = semantics.get("cross_references", {})
    if not isinstance(cross_references, dict):
        return
    bibliography = semantics.get("bibliography", {})
    enabled_kinds = {
        "figure": cross_references.get("figure_table_enabled") is True,
        "table": cross_references.get("figure_table_enabled") is True,
        "equation": bool(cross_references.get("equation_enabled", True)),
        "bibliography": bool(cross_references.get("bibliography_enabled", True))
        and bool(bibliography.get("output_block_present", False)),
    }

    registry = build_reference_registry(doc)
    for paragraph in doc.paragraphs:
        segments = parse_paragraph_segments(paragraph.text)
        if not any(segment.get("kind") == "cross_reference" for segment in segments):
            continue

        style_name = paragraph.style.name if getattr(paragraph, "style", None) else None
        clear_paragraph(paragraph)
        if style_name:
            paragraph.style = style_name

        for segment in segments:
            if segment.get("kind") != "cross_reference":
                paragraph.add_run(str(segment.get("text", "")))
                continue
            target_kind = str(segment.get("target_kind", ""))
            if not enabled_kinds.get(target_kind, False):
                paragraph.add_run(cross_reference_placeholder_text(segment))
                continue
            target_id = str(segment.get("target_id", ""))
            entry = registry.get(target_kind, {}).get(target_id)
            if entry is None:
                paragraph.add_run(cross_reference_placeholder_text(segment))
                continue
            append_reference_hyperlink(
                paragraph,
                bookmark_name=entry["bookmark"],
                label_text=entry["label"],
                prefix_text=str(segment.get("prefix", "") or ""),
            )


def bibliography_style_name(doc) -> str | None:
    available_styles = {
        style.name for style in doc.styles if getattr(style, "name", None)
    }
    for candidate in ("参考文献", "正文", "Normal"):
        if candidate in available_styles:
            return candidate
    return None


def normalize_reference_paragraph(paragraph, body_font: dict[str, str] | None) -> None:
    shared_module = importlib.import_module("docx.shared")
    Pt = shared_module.Pt
    paragraph.paragraph_format.left_indent = Pt(0)
    paragraph.paragraph_format.first_line_indent = Pt(0)
    paragraph.paragraph_format.line_spacing = 1.5
    reference_font = dict(body_font or {})
    reference_font["size"] = "21"
    apply_paragraph_font_settings(paragraph, reference_font)


def append_bibliography_output(
    doc, plan: dict[str, object], project_root: Path | str
) -> None:
    if not should_emit_bibliography(plan):
        return

    entries = load_bibliography_entries(project_root, plan)
    if not entries:
        return

    heading = next(
        (
            paragraph
            for paragraph in doc.paragraphs
            if strip_section_prefix(paragraph.text) in {"参考文献", "references"}
        ),
        None,
    )
    if heading is None:
        return

    style_name = bibliography_style_name(doc)
    available_styles = {
        style.name for style in doc.styles if getattr(style, "name", None)
    }
    body_font = style_font_settings(doc.styles, body_style_name(available_styles))
    last = heading
    for entry in entries:
        paragraph = insert_paragraph_after(last)
        if style_name:
            paragraph.style = style_name
        paragraph.add_run(entry["rendered_text"])
        add_bookmark(paragraph, entry["bookmark"])
        normalize_reference_paragraph(paragraph, body_font)
        last = paragraph


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build a redacted report from the selected template and body source."
    )
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--plan", default="config/template.plan.json")
    args = parser.parse_args()

    plan = load_json(project_path(args.project_root, args.plan))
    template_path = project_path(
        args.project_root, plan["selection"]["primary_template"].replace("./", "")
    )
    redacted_path = project_path(
        args.project_root, plan["selection"]["redacted_output"].replace("./", "")
    )
    body_path = project_path(
        args.project_root, plan["body_source"]["path"].replace("./", "")
    )

    if not template_path.exists():
        raise SystemExit(f"Template not found: {template_path}")
    if not body_path.exists():
        raise SystemExit(f"Body source not found: {body_path}")

    shutil.copy2(template_path, redacted_path)
    docx = import_docx()
    doc = docx.Document(redacted_path)

    blocks = markdown_to_blocks(body_path)
    code_theme = load_code_block_theme(args.project_root)
    code_status: dict[str, object] = {
        "styled": 0,
        "highlighted": 0,
        "unsupported": [],
        "warnings": list(code_theme.get("warnings", [])),
        "theme": {
            "name": code_theme["name"],
            "override_used": bool(code_theme.get("override_used", False)),
        },
    }
    equation_status: dict[str, object] = {"unsupported": []}
    image_status = {"inserted": [], "failed": []}
    fillable = plan.get("regions", {}).get("fillable", [])
    if fillable:
        image_status = render_blocks(
            doc,
            fillable[0],
            blocks,
            body_path.parent,
            code_theme,
            code_status,
            plan.get("semantics"),
            equation_status,
        )
    apply_toc_if_enabled(doc, plan)
    append_bibliography_output(doc, plan, args.project_root)
    apply_cross_reference_pass(doc, plan)
    doc.save(redacted_path)
    toc_refresh_status = {
        "attempted": bool(plan.get("semantics", {}).get("toc", {}).get("enabled")),
        "updated": False,
    }
    if toc_refresh_status["attempted"]:
        toc_refresh_status["updated"] = refresh_toc_with_word_if_available(
            redacted_path
        )
        if toc_refresh_status["updated"]:
            refreshed_doc = docx.Document(redacted_path)
            ensure_toc_styles(refreshed_doc)
            refreshed_doc.save(redacted_path)
    integrity_report = validate_docx_package(redacted_path)
    payload = {
        "redacted": str(redacted_path),
        "images": image_status,
        "code_blocks": code_status,
        "equations": equation_status,
        "toc_refresh": toc_refresh_status,
        "integrity": integrity_report,
    }
    if not integrity_report["ok"]:
        emit_json(payload)
        return 2
    emit_json(
        payload
    )
    return (
        1
        if image_status["failed"]
        or code_status["unsupported"]
        or equation_status["unsupported"]
        else 0
    )


if __name__ == "__main__":
    raise SystemExit(main())
