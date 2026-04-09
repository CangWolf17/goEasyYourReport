from __future__ import annotations

import importlib


def clear_paragraph(paragraph) -> None:
    for child in list(paragraph._element):
        paragraph._element.remove(child)


def word_qn(name: str) -> str:
    return importlib.import_module("docx.oxml.ns").qn(name)


def create_word_element(tag: str):
    return importlib.import_module("docx.oxml").OxmlElement(tag)


def set_paragraph_pagination(
    paragraph, *, keep_next: bool = False, keep_lines: bool = False
) -> None:
    p_pr = paragraph._p.get_or_add_pPr()

    def set_flag(tag: str, enabled: bool) -> None:
        element = p_pr.find(word_qn(tag))
        if not enabled:
            if element is not None:
                p_pr.remove(element)
            return
        if element is None:
            element = create_word_element(tag.replace("w:", "w:"))
            p_pr.append(element)

    set_flag("w:keepNext", keep_next)
    set_flag("w:keepLines", keep_lines)


def insert_paragraph_after(block):
    paragraph_module = importlib.import_module("docx.text.paragraph")
    xml_module = importlib.import_module("docx.oxml")
    new_p = xml_module.OxmlElement("w:p")
    if hasattr(block, "_p"):
        block._p.addnext(new_p)
        parent = block._parent
    else:
        block._tbl.addnext(new_p)
        parent = block._parent
    return paragraph_module.Paragraph(new_p, parent)


def insert_paragraph_before(block):
    paragraph_module = importlib.import_module("docx.text.paragraph")
    xml_module = importlib.import_module("docx.oxml")
    new_p = xml_module.OxmlElement("w:p")
    if hasattr(block, "_p"):
        block._p.addprevious(new_p)
        parent = block._parent
    else:
        block._tbl.addprevious(new_p)
        parent = block._parent
    return paragraph_module.Paragraph(new_p, parent)
