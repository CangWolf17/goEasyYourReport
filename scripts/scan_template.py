from __future__ import annotations

import argparse
import re
from pathlib import Path
import sys

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts._shared import dump_json, emit_json, import_docx, load_json, project_path


def is_heading_like(style_name: str, text: str) -> bool:
    lowered = style_name.lower()
    if "heading" in lowered or style_name in {"标题2", "标题3", "标题4"}:
        return True
    return bool(
        re.match(r"^(\d+(\.\d+)*)\s", text)
        or re.match(r"^[一二三四五六七八九十]+、", text)
    )


def is_field_candidate(text: str) -> bool:
    stripped = text.strip()
    if not stripped:
        return False
    return stripped.endswith(":") or stripped.endswith("：")


def analyze_docx(template_path: Path) -> dict[str, object]:
    docx = import_docx()
    doc = docx.Document(template_path)
    paragraphs = []
    heading_anchors = []
    field_candidates = []
    first_heading_index = None
    for index, paragraph in enumerate(doc.paragraphs):
        text = paragraph.text.strip()
        style_name = paragraph.style.name if paragraph.style is not None else ""
        paragraphs.append(
            {
                "index": index,
                "style": style_name,
                "text": text,
            }
        )
        if text and is_heading_like(style_name, text):
            heading_anchors.append(
                {
                    "kind": "heading",
                    "paragraph": index,
                    "style": style_name,
                    "text": text,
                }
            )
        if is_field_candidate(text):
            field_candidates.append(
                {
                    "kind": "field_candidate",
                    "paragraph": index,
                    "style": style_name,
                    "text": text,
                }
            )
        if first_heading_index is None and text and is_heading_like(style_name, text):
            first_heading_index = index

    if first_heading_index is None:
        first_heading_index = min(len(paragraphs), 12) if paragraphs else 0

    locked = []
    fillable = []
    if paragraphs and first_heading_index > 0:
        locked.append(
            {
                "id": "cover",
                "reason": "template-scan",
                "start_paragraph": 0,
                "end_paragraph": first_heading_index - 1,
            }
        )
    if paragraphs and first_heading_index < len(paragraphs):
        fillable.append(
            {
                "id": "body_main",
                "source": "./docs/report_body.md",
                "start_paragraph": first_heading_index,
                "end_paragraph": len(paragraphs) - 1,
            }
        )

    region_candidates = []
    if paragraphs and first_heading_index < len(paragraphs):
        region_candidates.append(
            {
                "kind": "boundary",
                "paragraph": first_heading_index,
                "reason": "first-heading-like-paragraph",
                "locked_before": "cover",
                "fillable_after": "body_main",
            }
        )

    return {
        "template": str(template_path),
        "paragraph_count": len(paragraphs),
        "first_heading_index": first_heading_index,
        "paragraphs": paragraphs,
        "anchors": {
            "headings": heading_anchors,
            "field_candidates": field_candidates,
            "region_candidates": region_candidates,
        },
        "regions": {
            "locked": locked,
            "fillable": fillable,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Scan a DOCX template and update template planning data."
    )
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--template", default=None)
    parser.add_argument("--plan", default="config/template.plan.json")
    parser.add_argument("--scan-output", default="logs/template_scan.json")
    args = parser.parse_args()

    plan_path = project_path(args.project_root, args.plan)
    plan = load_json(plan_path)
    template_path = (
        Path(args.template).resolve()
        if args.template
        else project_path(
            args.project_root, plan["selection"]["primary_template"].replace("./", "")
        )
    )
    if not template_path.exists():
        raise SystemExit(f"Template not found: {template_path}")

    scan = analyze_docx(template_path)
    regions = scan["regions"]
    anchors = scan["anchors"]
    paragraph_count = scan["paragraph_count"]
    first_heading_index = scan["first_heading_index"]
    if not isinstance(regions, dict):
        raise SystemExit("Template scan produced invalid region data.")
    plan["regions"] = regions
    plan_anchors = plan.setdefault("anchors", {})
    if not isinstance(plan_anchors, dict):
        raise SystemExit("Template plan anchors must be an object.")
    plan_anchors["headings"] = anchors.get("headings", [])
    plan_anchors["field_candidates"] = anchors.get("field_candidates", [])
    plan_anchors["region_candidates"] = anchors.get("region_candidates", [])
    plan.setdefault("status", {})["template_scanned"] = True
    dump_json(plan_path, plan)
    dump_json(project_path(args.project_root, args.scan_output), scan)
    emit_json(
        {
            "template": str(template_path),
            "paragraph_count": paragraph_count,
            "first_heading_index": first_heading_index,
            "anchors": anchors,
            "locked_regions": regions.get("locked", []),
            "fillable_regions": regions.get("fillable", []),
        }
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
