from __future__ import annotations

import importlib

from scripts._docx_xml import word_qn


def preferred_style_name(available_styles: set[str], *candidates: str) -> str | None:
    for candidate in candidates:
        if candidate in available_styles:
            return candidate
    return None


def preferred_heading_style(level: int, available_styles: set[str]) -> str | None:
    level = max(1, min(level, 4))
    style_map = {
        1: ("标题2", "Heading 1"),
        2: ("标题3", "Heading 2"),
        3: ("标题4", "Heading 3"),
        4: ("标题4", "Heading 4"),
    }
    return preferred_style_name(available_styles, *style_map[level])


def title_style_name(available_styles: set[str]) -> str | None:
    return preferred_style_name(available_styles, "题目", "Title", "Heading 1", "标题2")


def body_style_name(available_styles: set[str]) -> str | None:
    return preferred_style_name(available_styles, "正文", "Normal")


def figure_caption_style_name(available_styles: set[str]) -> str | None:
    return preferred_style_name(available_styles, "图题", "Caption")


def table_caption_style_name(available_styles: set[str]) -> str | None:
    return preferred_style_name(available_styles, "表题", "Caption")


def reference_style_name(available_styles: set[str]) -> str | None:
    return preferred_style_name(available_styles, "参考文献", "正文", "Normal")


def style_font_settings(styles, style_name: str | None) -> dict[str, str] | None:
    if not style_name:
        return None
    try:
        style = styles[style_name]
    except KeyError:
        return None
    r_pr = style.element.find(word_qn("w:rPr"))
    if r_pr is None:
        return None
    r_fonts = r_pr.find(word_qn("w:rFonts"))
    size = r_pr.find(word_qn("w:sz"))
    settings = {
        "ascii": None if r_fonts is None else r_fonts.get(word_qn("w:ascii")),
        "hAnsi": None if r_fonts is None else r_fonts.get(word_qn("w:hAnsi")),
        "eastAsia": None if r_fonts is None else r_fonts.get(word_qn("w:eastAsia")),
        "size": None if size is None else size.get(word_qn("w:val")),
    }
    if not any(settings.values()):
        return None
    return settings


def apply_run_font_settings(run, font_settings: dict[str, str] | None) -> None:
    if not font_settings:
        return
    shared_module = importlib.import_module("docx.shared")
    xml_module = importlib.import_module("docx.oxml")
    Pt = shared_module.Pt

    r_pr = run._r.get_or_add_rPr()
    r_fonts = r_pr.find(word_qn("w:rFonts"))
    if r_fonts is None:
        r_fonts = xml_module.OxmlElement("w:rFonts")
        r_pr.append(r_fonts)

    primary_name = (
        font_settings.get("ascii")
        or font_settings.get("hAnsi")
        or font_settings.get("eastAsia")
    )
    if primary_name:
        run.font.name = primary_name

    for key in ("ascii", "hAnsi", "eastAsia"):
        value = font_settings.get(key)
        if value:
            r_fonts.set(word_qn(f"w:{key}"), value)

    size = font_settings.get("size")
    if size:
        run.font.size = Pt(int(size) / 2)
        sz = r_pr.find(word_qn("w:sz"))
        if sz is None:
            sz = xml_module.OxmlElement("w:sz")
            r_pr.append(sz)
        sz.set(word_qn("w:val"), size)
        sz_cs = r_pr.find(word_qn("w:szCs"))
        if sz_cs is None:
            sz_cs = xml_module.OxmlElement("w:szCs")
            r_pr.append(sz_cs)
        sz_cs.set(word_qn("w:val"), size)


def apply_paragraph_font_settings(
    paragraph, font_settings: dict[str, str] | None
) -> None:
    if not font_settings:
        return
    for run in paragraph.runs:
        apply_run_font_settings(run, font_settings)
