from __future__ import annotations

import argparse
from copy import deepcopy
import shutil
import sys
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts._shared import dump_json, emit_json, import_docx, load_json, project_path


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
    for style in styles_root.findall(qn("style")):
        if style_name(style) == target_name:
            return style
    return None


def replace_or_append_style(
    styles_root: ET.Element,
    donor_style: ET.Element,
    *,
    style_name_value: str,
) -> None:
    existing = style_by_name(styles_root, style_name_value)
    donor_copy = deepcopy(donor_style)
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
    donor_style_names = style_names(donor_template)
    missing_styles = [
        name for name in TARGET_STYLE_NAMES if name not in user_style_names
    ]
    copied_styles = [name for name in missing_styles if name in donor_style_names]
    unresolved_styles = [
        name for name in missing_styles if name not in donor_style_names
    ]

    with zipfile.ZipFile(user_template, "r") as user_zip:
        user_styles_root = ET.fromstring(user_zip.read("word/styles.xml"))
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

    replaced_styles: list[str] = []
    for style_name_value in copied_styles:
        donor_style = donor_styles.get(style_name_value)
        if donor_style is None:
            continue
        replace_or_append_style(
            user_styles_root,
            donor_style,
            style_name_value=style_name_value,
        )

    for style_name_value, expected_outline in OUTLINE_STYLE_LEVELS.items():
        donor_style = donor_styles.get(style_name_value)
        user_style = style_by_name(user_styles_root, style_name_value)
        if donor_style is None or user_style is None:
            continue
        if outline_level(user_style) != expected_outline:
            replace_or_append_style(
                user_styles_root,
                donor_style,
                style_name_value=style_name_value,
            )
            if style_name_value not in copied_styles:
                replaced_styles.append(style_name_value)

    user_entries["word/styles.xml"] = ET.tostring(
        user_styles_root, encoding="utf-8", xml_declaration=True
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


def apply_recommendation(plan_path: Path, recommendation: dict[str, object]) -> None:
    plan = load_json(plan_path)
    selection = plan.setdefault("selection", {})
    selection["primary_template"] = recommendation["recommended_template"]
    status = plan.setdefault("status", {})
    status["template_recommendation_applied"] = True
    dump_json(plan_path, plan)


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
        apply_recommendation(plan_path, recommendation)
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
