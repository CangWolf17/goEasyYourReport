from __future__ import annotations

from itertools import count

from scripts._docx_xml import create_word_element, word_qn


_BOOKMARK_IDS = count(1)


def _append_field_char(run_element, kind: str) -> None:
    field_char = create_word_element("w:fldChar")
    field_char.set(word_qn("w:fldCharType"), kind)
    run_element.append(field_char)


def _append_text_run(paragraph, text: str) -> None:
    run = paragraph.add_run()
    run.text = text


def add_bookmark(paragraph, bookmark_name: str) -> None:
    bookmark_id = str(next(_BOOKMARK_IDS))
    start = create_word_element("w:bookmarkStart")
    start.set(word_qn("w:id"), bookmark_id)
    start.set(word_qn("w:name"), bookmark_name)
    end = create_word_element("w:bookmarkEnd")
    end.set(word_qn("w:id"), bookmark_id)
    insert_at = 1 if paragraph._p.find(word_qn("w:pPr")) is not None else 0
    paragraph._p.insert(insert_at, start)
    paragraph._p.append(end)


def append_complex_field(
    paragraph, instruction: str, display_text: str | None = None
) -> None:
    begin_run = create_word_element("w:r")
    _append_field_char(begin_run, "begin")
    paragraph._p.append(begin_run)

    instruction_run = create_word_element("w:r")
    instruction_text = create_word_element("w:instrText")
    instruction_text.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
    instruction_text.text = instruction
    instruction_run.append(instruction_text)
    paragraph._p.append(instruction_run)

    separate_run = create_word_element("w:r")
    _append_field_char(separate_run, "separate")
    paragraph._p.append(separate_run)

    if display_text is not None:
        _append_text_run(paragraph, display_text)

    end_run = create_word_element("w:r")
    _append_field_char(end_run, "end")
    paragraph._p.append(end_run)


def insert_toc_field(paragraph, levels: tuple[int, int]) -> None:
    start_level, end_level = levels
    instruction = f' TOC \\o "{start_level}-{end_level}" \\h \\z \\u '
    append_complex_field(paragraph, instruction, display_text="目录")


def append_reference_field(
    paragraph,
    *,
    bookmark_name: str,
    label_text: str,
    prefix_text: str | None = None,
) -> None:
    visible_prefix = (prefix_text or "").strip()
    if visible_prefix and label_text and visible_prefix.endswith(label_text[:1]):
        visible_prefix = visible_prefix[: -len(label_text[:1])]
    if visible_prefix:
        _append_text_run(paragraph, visible_prefix)
    append_complex_field(
        paragraph,
        f" REF {bookmark_name} \\h ",
        display_text=label_text,
    )


def append_reference_hyperlink(
    paragraph,
    *,
    bookmark_name: str,
    label_text: str,
    prefix_text: str | None = None,
) -> None:
    visible_prefix = (prefix_text or "").strip()
    if visible_prefix and label_text and visible_prefix.endswith(label_text[:1]):
        visible_prefix = visible_prefix[: -len(label_text[:1])]
    if visible_prefix:
        _append_text_run(paragraph, visible_prefix)

    hyperlink = create_word_element("w:hyperlink")
    hyperlink.set(word_qn("w:anchor"), bookmark_name)
    hyperlink.set(word_qn("w:history"), "1")

    run = create_word_element("w:r")
    text = create_word_element("w:t")
    text.text = label_text
    run.append(text)
    hyperlink.append(run)
    paragraph._p.append(hyperlink)


def enable_update_fields_on_open(doc) -> None:
    settings_part = getattr(doc._part, "_settings_part", None)
    if settings_part is None:
        return None
    settings = settings_part.element
    update_fields = settings.find(word_qn("w:updateFields"))
    if update_fields is None:
        update_fields = create_word_element("w:updateFields")
        settings.append(update_fields)
    update_fields.set(word_qn("w:val"), "true")
    return None
