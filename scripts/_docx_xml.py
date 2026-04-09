from __future__ import annotations

import importlib


def clear_paragraph(paragraph) -> None:
    for child in list(paragraph._element):
        paragraph._element.remove(child)


def word_qn(name: str) -> str:
    return importlib.import_module("docx.oxml.ns").qn(name)


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
