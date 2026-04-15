from __future__ import annotations

import argparse
from copy import deepcopy
import re
import shutil
import sys
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts._shared import (
    PROJECT_ROOT,
    dump_json,
    emit_json,
    import_docx,
    load_json,
    project_path,
    run_python_script,
)
from scripts._task_contract import sync_template_authority_mirrors


W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
TARGET_STYLE_NAMES = [
    "题目",
    "标题2",
    "标题3",
    "标题4",
    "正文",
    "列表编号",
    "列表符号",
    "图题",
    "表题",
    "参考文献",
    "Caption",
]
OUTLINE_STYLE_LEVELS = {
    "题目": None,
    "标题2": 0,
    "标题3": 1,
    "标题4": 2,
}
FALLBACK_STYLE_SOURCES = {
    "题目": ("Title",),
    "标题2": ("Heading 1",),
    "标题3": ("Heading 2",),
    "标题4": ("Heading 3",),
    "正文": ("Body Text", "Normal"),
    "列表编号": ("List Number",),
    "列表符号": ("List Bullet",),
    "图题": ("Caption",),
    "表题": ("Caption",),
    "参考文献": ("Body Text", "Normal"),
    "Caption": ("Caption",),
}
STYLE_REFERENCE_ATTRIBUTES = ("basedOn", "next", "link")
STYLE_XML_DECLARATION_PATTERN = re.compile(rb"^<\?xml[^?]*\?>")
STYLE_XML_ROOT_PATTERN = re.compile(rb"<w:styles\b[^>]*>")
STYLE_XML_ANY_ROOT_PATTERN = re.compile(rb"<(?:\w+:)?styles\b[^>]*>")
IGNORABLE_PATTERN = re.compile(rb'\b(?:\w+:)?Ignorable="([^"]+)"')
STYLE_XML_NAMESPACES = {
    "mc": "http://schemas.openxmlformats.org/markup-compatibility/2006",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "w": W_NS,
    "w14": "http://schemas.microsoft.com/office/word/2010/wordml",
    "w15": "http://schemas.microsoft.com/office/word/2012/wordml",
    "w16": "http://schemas.microsoft.com/office/word/2018/wordml",
    "w16cex": "http://schemas.microsoft.com/office/word/2018/wordml/cex",
    "w16cid": "http://schemas.microsoft.com/office/word/2016/wordml/cid",
    "w16sdtdh": "http://schemas.microsoft.com/office/word/2020/wordml/sdtdatahash",
    "w16se": "http://schemas.microsoft.com/office/word/2015/wordml/symex",
}


def qn(local_name: str) -> str:
    return f"{{{W_NS}}}{local_name}"


def normalize_repo_relative(path_text: str) -> str:
    normalized = Path(path_text).as_posix()
    if normalized.startswith("./"):
        return normalized
    return f"./{normalized.lstrip('./')}"


def style_names(docx_path: Path) -> set[str]:
    docx = import_docx()
    doc = docx.Document(docx_path)
    return {style.name for style in doc.styles if getattr(style, "name", None)}


def style_name(style_element: ET.Element) -> str | None:
    name_element = style_element.find(qn("name"))
    if name_element is None:
        return None
    return name_element.get(qn("val"))


def attribute_name(element: ET.Element, local_name: str) -> str:
    if qn(local_name) in element.attrib:
        return qn(local_name)
    if local_name in element.attrib:
        return local_name
    return qn(local_name)


def attribute_value(element: ET.Element, local_name: str) -> str | None:
    return element.get(qn(local_name)) or element.get(local_name)


def style_id(style_element: ET.Element) -> str | None:
    return attribute_value(style_element, "styleId")


def set_style_id(style_element: ET.Element, value: str) -> None:
    style_element.set(attribute_name(style_element, "styleId"), value)


def set_style_name(style_element: ET.Element, value: str) -> None:
    name_element = style_element.find(qn("name"))
    if name_element is None:
        name_element = ET.Element(qn("name"))
        style_element.insert(0, name_element)
    name_element.set(qn("val"), value)


def ensure_paragraph_properties(style_element: ET.Element) -> ET.Element:
    p_pr = style_element.find(qn("pPr"))
    if p_pr is None:
        p_pr = ET.Element(qn("pPr"))
        style_element.append(p_pr)
    return p_pr


def set_outline_level(style_element: ET.Element, expected_level: int | None) -> None:
    p_pr = ensure_paragraph_properties(style_element)
    outline = p_pr.find(qn("outlineLvl"))
    if expected_level is None:
        if outline is not None:
            p_pr.remove(outline)
        return
    if outline is None:
        outline = ET.Element(qn("outlineLvl"))
        p_pr.append(outline)
    outline.set(qn("val"), str(expected_level))


def outline_level(style_element: ET.Element) -> int | None:
    p_pr = style_element.find(qn("pPr"))
    if p_pr is None:
        return None
    outline = p_pr.find(qn("outlineLvl"))
    if outline is None:
        return None
    raw = outline.get(qn("val"))
    return None if raw is None else int(raw)


def style_by_name(styles_root: ET.Element, target_name: str) -> ET.Element | None:
    target_key = target_name.casefold()
    for style in styles_root.findall(qn("style")):
        current_name = style_name(style)
        if current_name is not None and current_name.casefold() == target_key:
            return style
    return None


def clone_style_for_target(source_style: ET.Element, target_name: str) -> ET.Element:
    style_copy = deepcopy(source_style)
    set_style_name(style_copy, target_name)
    set_style_id(style_copy, target_name)
    set_outline_level(style_copy, OUTLINE_STYLE_LEVELS.get(target_name))
    return style_copy


def style_ids_by_name(styles_root: ET.Element) -> dict[str, str]:
    return {
        name: style_identifier
        for style in styles_root.findall(qn("style"))
        for name in [style_name(style)]
        for style_identifier in [style_id(style)]
        if name and style_identifier
    }


def style_names_by_id(styles_root: ET.Element) -> dict[str, str]:
    return {
        style_identifier: name
        for style in styles_root.findall(qn("style"))
        for name in [style_name(style)]
        for style_identifier in [style_id(style)]
        if name and style_identifier
    }


def remap_style_references(
    style_element: ET.Element,
    *,
    donor_style_names_by_id: dict[str, str],
    final_style_ids_by_name: dict[str, str],
) -> None:
    for attribute in STYLE_REFERENCE_ATTRIBUTES:
        dependency = style_element.find(qn(attribute))
        if dependency is None:
            continue
        target_style_id = attribute_value(dependency, "val")
        if not target_style_id:
            continue
        target_style_name = donor_style_names_by_id.get(target_style_id)
        if target_style_name is None:
            continue
        mapped_style_id = final_style_ids_by_name.get(target_style_name)
        if mapped_style_id is None:
            continue
        dependency.set(attribute_name(dependency, "val"), mapped_style_id)


def register_style_xml_namespaces() -> None:
    for prefix, uri in STYLE_XML_NAMESPACES.items():
        ET.register_namespace(prefix, uri)


def serialize_styles_xml(styles_root: ET.Element, *, original_xml: bytes) -> bytes:
    register_style_xml_namespaces()
    serialized = ET.tostring(styles_root, encoding="utf-8", xml_declaration=True)

    original_declaration = STYLE_XML_DECLARATION_PATTERN.search(original_xml)
    if original_declaration is not None:
        serialized = STYLE_XML_DECLARATION_PATTERN.sub(
            original_declaration.group(0),
            serialized,
            count=1,
        )

    original_root = STYLE_XML_ROOT_PATTERN.search(original_xml)
    serialized_root = STYLE_XML_ROOT_PATTERN.search(serialized)
    if original_root is not None and serialized_root is not None:
        serialized = (
            serialized[: serialized_root.start()]
            + original_root.group(0)
            + serialized[serialized_root.end() :]
        )

    serialized = ensure_ignorable_namespace_declarations(serialized)
    return serialized


def ensure_ignorable_namespace_declarations(serialized: bytes) -> bytes:
    root_match = STYLE_XML_ANY_ROOT_PATTERN.search(serialized)
    if root_match is None:
        return serialized

    root_tag = root_match.group(0).decode("utf-8")
    ignorable_match = IGNORABLE_PATTERN.search(root_match.group(0))
    if ignorable_match is None:
        return serialized

    additions: list[str] = []
    for prefix in ignorable_match.group(1).decode("utf-8").split():
        if f"xmlns:{prefix}=" in root_tag:
            continue
        namespace = STYLE_XML_NAMESPACES.get(prefix)
        if namespace is None:
            continue
        additions.append(f' xmlns:{prefix}="{namespace}"')

    if not additions:
        return serialized

    patched_root = (root_tag[:-1] + "".join(additions) + ">").encode("utf-8")
    return (
        serialized[: root_match.start()]
        + patched_root
        + serialized[root_match.end() :]
    )


def replace_or_append_style(
    styles_root: ET.Element,
    donor_style: ET.Element,
    *,
    style_name_value: str,
    donor_style_names_by_id: dict[str, str],
    final_style_ids_by_name: dict[str, str],
) -> None:
    existing = style_by_name(styles_root, style_name_value)
    donor_copy = deepcopy(donor_style)
    existing_style_id = None if existing is None else style_id(existing)
    final_style_id = (
        final_style_ids_by_name.get(style_name_value)
        or existing_style_id
        or style_id(donor_copy)
    )
    if final_style_id is not None:
        set_style_id(donor_copy, final_style_id)
        final_style_ids_by_name[style_name_value] = final_style_id
    remap_style_references(
        donor_copy,
        donor_style_names_by_id=donor_style_names_by_id,
        final_style_ids_by_name=final_style_ids_by_name,
    )
    if existing is None:
        styles_root.append(donor_copy)
        return
    index = list(styles_root).index(existing)
    styles_root.remove(existing)
    styles_root.insert(index, donor_copy)


def merge_missing_styles(
    user_template: Path, donor_template: Path, recommended_template: Path
) -> tuple[list[str], list[str], list[str]]:
    user_style_names = style_names(user_template)
    missing_styles = [
        name for name in TARGET_STYLE_NAMES if name not in user_style_names
    ]

    with zipfile.ZipFile(user_template, "r") as user_zip:
        user_styles_xml = user_zip.read("word/styles.xml")
        user_styles_root = ET.fromstring(user_styles_xml)
        user_entries = {
            info.filename: user_zip.read(info.filename) for info in user_zip.infolist()
        }

    with zipfile.ZipFile(donor_template, "r") as donor_zip:
        donor_styles_root = ET.fromstring(donor_zip.read("word/styles.xml"))

    donor_styles = {
        name: style
        for style in donor_styles_root.findall(qn("style"))
        for name in [style_name(style)]
        if name
    }
    donor_style_names_by_id = style_names_by_id(donor_styles_root)
    user_style_names_by_id = style_names_by_id(user_styles_root)

    def style_source_for_target(
        style_name_value: str,
    ) -> tuple[ET.Element, dict[str, str]] | None:
        donor_style = donor_styles.get(style_name_value)
        if donor_style is not None:
            return (
                clone_style_for_target(donor_style, style_name_value),
                donor_style_names_by_id,
            )
        for styles_root, names_by_id in (
            (donor_styles_root, donor_style_names_by_id),
            (user_styles_root, user_style_names_by_id),
        ):
            for fallback_name in FALLBACK_STYLE_SOURCES.get(style_name_value, ()):
                fallback_style = style_by_name(styles_root, fallback_name)
                if fallback_style is None:
                    continue
                return (
                    clone_style_for_target(fallback_style, style_name_value),
                    names_by_id,
                )
        return None

    style_sources = {
        style_name_value: source
        for style_name_value in TARGET_STYLE_NAMES
        for source in [style_source_for_target(style_name_value)]
        if source is not None
    }
    copied_styles = [name for name in missing_styles if name in style_sources]
    unresolved_styles = [name for name in missing_styles if name not in style_sources]

    outline_replacements = []
    for style_name_value, expected_outline in OUTLINE_STYLE_LEVELS.items():
        user_style = style_by_name(user_styles_root, style_name_value)
        if style_name_value not in style_sources or user_style is None:
            continue
        if outline_level(user_style) != expected_outline:
            outline_replacements.append(style_name_value)

    final_style_ids_by_name = style_ids_by_name(user_styles_root)
    for style_name_value in set(copied_styles + outline_replacements):
        donor_style, _ = style_sources[style_name_value]
        existing = style_by_name(user_styles_root, style_name_value)
        existing_style_id = None if existing is None else style_id(existing)
        donor_style_id = style_id(donor_style)
        final_style_id = existing_style_id or donor_style_id
        if final_style_id is not None:
            final_style_ids_by_name[style_name_value] = final_style_id

    replaced_styles: list[str] = []
    for style_name_value in copied_styles:
        donor_style, donor_style_names = style_sources[style_name_value]
        replace_or_append_style(
            user_styles_root,
            donor_style,
            style_name_value=style_name_value,
            donor_style_names_by_id=donor_style_names,
            final_style_ids_by_name=final_style_ids_by_name,
        )

    for style_name_value in outline_replacements:
        donor_style, donor_style_names = style_sources[style_name_value]
        replace_or_append_style(
            user_styles_root,
            donor_style,
            style_name_value=style_name_value,
            donor_style_names_by_id=donor_style_names,
            final_style_ids_by_name=final_style_ids_by_name,
        )
        if style_name_value not in copied_styles:
            replaced_styles.append(style_name_value)

    user_entries["word/styles.xml"] = serialize_styles_xml(
        user_styles_root,
        original_xml=user_styles_xml,
    )

    recommended_template.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(
        recommended_template, "w", compression=zipfile.ZIP_DEFLATED
    ) as output_zip:
        for filename, content in user_entries.items():
            output_zip.writestr(filename, content)

    return (
        missing_styles,
        copied_styles + [name for name in replaced_styles if name not in copied_styles],
        unresolved_styles,
    )


def build_recommendation_payload(
    project_root: Path,
    plan: dict[str, object],
    user_template: Path,
    donor_template: Path,
    recommended_template: Path,
    missing_styles: list[str],
    copied_styles: list[str],
    unresolved_styles: list[str],
) -> dict[str, object]:
    user_relative = normalize_repo_relative(
        str(user_template.relative_to(project_root))
    )
    donor_relative = normalize_repo_relative(
        str(donor_template.relative_to(project_root))
    )
    recommended_relative = normalize_repo_relative(
        str(recommended_template.relative_to(project_root))
    )
    current_primary = str(
        plan.get("selection", {}).get("primary_template", user_relative)
    )
    recommended_active = current_primary == recommended_relative
    return {
        "user_template": user_relative,
        "donor_template": donor_relative,
        "recommended_template": recommended_relative,
        "target_styles": TARGET_STYLE_NAMES,
        "user_present_styles": sorted(style_names(user_template)),
        "donor_present_styles": sorted(style_names(donor_template)),
        "missing_styles": missing_styles,
        "copied_styles": copied_styles,
        "unresolved_styles": unresolved_styles,
        "current_primary_template": current_primary,
        "recommended_active": recommended_active,
        "pending_acceptance": bool(copied_styles) and not recommended_active,
    }


def apply_recommendation(
    project_root: Path, plan_path: Path, recommendation: dict[str, object]
) -> None:
    plan = load_json(plan_path)
    selection = plan.setdefault("selection", {})
    selection["primary_template"] = recommendation["recommended_template"]
    status = plan.setdefault("status", {})
    status["template_recommendation_applied"] = True
    dump_json(plan_path, plan)
    sync_template_authority_mirrors(project_root)


def ensure_initialized_workspace(project_root: Path, plan_path: Path) -> None:
    if plan_path.exists():
        return

    init_result = run_python_script(
        PROJECT_ROOT / "scripts" / "init_project.py",
        "--project-root",
        str(project_root),
    )
    if init_result["returncode"] != 0:
        details = (
            init_result.get("stderr")
            or init_result.get("stdout")
            or "init_project.py failed while bootstrapping workspace"
        )
        raise SystemExit(str(details))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate and optionally apply a recommended template with backfilled styles."
    )
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--plan", default="config/template.plan.json")
    parser.add_argument("--user-template", default="templates/template.user.docx")
    parser.add_argument("--donor-template", default="templates/template.sample.docx")
    parser.add_argument(
        "--recommended-template", default="templates/template.recommended.docx"
    )
    parser.add_argument(
        "--report-output", default="logs/template_style_recommendation.json"
    )
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    project_root = Path(args.project_root).resolve()
    plan_path = project_path(project_root, args.plan)
    ensure_initialized_workspace(project_root, plan_path)
    plan = load_json(plan_path)
    user_template = project_path(project_root, args.user_template)
    donor_template = project_path(project_root, args.donor_template)
    recommended_template = project_path(project_root, args.recommended_template)
    report_output = project_path(project_root, args.report_output)

    if not user_template.exists():
        raise SystemExit(f"User template not found: {user_template}")
    if not donor_template.exists():
        raise SystemExit(f"Donor template not found: {donor_template}")

    missing_styles, copied_styles, unresolved_styles = merge_missing_styles(
        user_template, donor_template, recommended_template
    )
    recommendation = build_recommendation_payload(
        project_root,
        plan,
        user_template,
        donor_template,
        recommended_template,
        missing_styles,
        copied_styles,
        unresolved_styles,
    )

    if args.apply:
        apply_recommendation(project_root, plan_path, recommendation)
        plan = load_json(plan_path)
        recommendation = build_recommendation_payload(
            project_root,
            plan,
            user_template,
            donor_template,
            recommended_template,
            missing_styles,
            copied_styles,
            unresolved_styles,
        )

    dump_json(report_output, recommendation)
    emit_json(recommendation)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
