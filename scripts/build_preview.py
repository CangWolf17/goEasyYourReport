from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts._docx_xml import (
    clear_paragraph,
    insert_paragraph_after,
    insert_paragraph_before,
)
from scripts._docx_semantics import ensure_plan_semantics
from scripts._shared import dump_json, emit_json, import_docx, load_json, project_path


def normalize_repo_relative(path_text: str) -> str:
    normalized = Path(path_text).as_posix()
    if normalized.startswith("./"):
        return normalized
    return f"./{normalized.lstrip('./')}"


def build_summary(
    plan: dict[str, object],
    binding: dict[str, object],
    summary_relative: str,
    preview_relative: str,
    template_recommendation: dict[str, object] | None = None,
) -> dict[str, object]:
    anchors = plan.get("anchors", {})
    if not isinstance(anchors, dict):
        anchors = {}

    bindings = binding.get("bindings", [])
    availability = binding.get("availability", {})
    if not isinstance(bindings, list):
        bindings = []
    if not isinstance(availability, dict):
        availability = {}
    semantics = ensure_plan_semantics(plan)
    template_scan = semantics.get("template_scan", {})
    style_candidates = template_scan.get("style_candidates", {})
    style_gaps = template_scan.get("style_gaps", [])
    outline_complete = bool(template_scan.get("outline_semantics_complete", False))
    toc = semantics.get("toc", {})
    reference_block = {
        "present": bool(template_scan.get("reference_block_present", False))
    }
    cross_references = semantics.get("cross_references", {})
    bibliography = semantics.get("bibliography", {})

    needs_confirmation = []
    if not plan.get("regions", {}).get("fillable", []):
        needs_confirmation.append("no fillable regions detected")
    if not anchors.get("field_candidates", []):
        needs_confirmation.append("no field candidates detected")
    if not bindings:
        needs_confirmation.append("no field bindings configured")
    if template_recommendation and template_recommendation.get("pending_acceptance"):
        needs_confirmation.append("template style recommendation pending")
    if not outline_complete:
        needs_confirmation.append("template outline semantics incomplete")
    if any(gap in {"列表编号", "列表符号"} for gap in style_gaps):
        needs_confirmation.append("list style semantics unresolved")
    if toc.get("detected") and toc.get("needs_confirmation", False):
        needs_confirmation.append("toc detected; confirm whether to enable")
    if cross_references.get("figure_table_enabled") == "needs_confirmation":
        needs_confirmation.append(
            "confirm whether to insert figure/table cross references"
        )
    if (
        bibliography.get("output_block_present")
        and bibliography.get("source_mode") == "needs_confirmation"
    ):
        needs_confirmation.append("confirm bibliography source mode")

    return {
        "version": "1.0",
        "template": plan["selection"]["primary_template"],
        "preview": preview_relative,
        "summary": summary_relative,
        "regions": plan.get("regions", {}),
        "anchors": anchors,
        "field_binding": {
            "path": plan["field_binding"]["path"],
            "bindings": bindings,
            "availability": availability,
        },
        "semantics": {
            "style_candidates": style_candidates,
            "style_gaps": style_gaps,
            "outline_semantics_complete": outline_complete,
            "toc": {
                "detected": bool(toc.get("detected", False)),
                "kind": toc.get("kind", "none"),
                "enabled": bool(toc.get("enabled", False)),
                "needs_confirmation": bool(toc.get("needs_confirmation", False)),
            },
            "reference_block": reference_block,
            "cross_references": {
                "figure_table_enabled": cross_references.get(
                    "figure_table_enabled", "needs_confirmation"
                )
            },
            "bibliography": {
                "source_mode": bibliography.get(
                    "source_mode", "needs_confirmation"
                ),
                "output_block_present": bool(
                    bibliography.get("output_block_present", False)
                ),
            },
        },
        "template_recommendation": template_recommendation or {},
        "review": {
            "warnings": [],
            "needs_confirmation": needs_confirmation,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build a preview DOCX with fillable regions replaced by placeholders."
    )
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--plan", default="config/template.plan.json")
    args = parser.parse_args()

    plan = load_json(project_path(args.project_root, args.plan))
    template_path = project_path(
        args.project_root, plan["selection"]["primary_template"].replace("./", "")
    )
    preview_path = project_path(
        args.project_root, plan["selection"]["preview_output"].replace("./", "")
    )
    summary_path = preview_path.with_suffix(".summary.json")
    binding_path = project_path(
        args.project_root, plan["field_binding"]["path"].replace("./", "")
    )

    if not template_path.exists():
        raise SystemExit(f"Template not found: {template_path}")
    if not binding_path.exists():
        raise SystemExit(f"Field binding not found: {binding_path}")

    binding = load_json(binding_path)
    recommendation_path = project_path(
        args.project_root, "logs/template_style_recommendation.json"
    )
    template_recommendation = (
        load_json(recommendation_path) if recommendation_path.exists() else None
    )

    shutil.copy2(template_path, preview_path)
    docx = import_docx()
    doc = docx.Document(preview_path)
    original_paragraphs = list(doc.paragraphs)
    locked = plan.get("regions", {}).get("locked", [])
    for region in reversed(locked):
        start = region.get("start_paragraph")
        end = region.get("end_paragraph")
        if start is None or end is None or start >= len(original_paragraphs):
            continue
        start_paragraph = original_paragraphs[start]
        end_index = min(end, len(original_paragraphs) - 1)
        end_paragraph = original_paragraphs[end_index]
        marker_start = insert_paragraph_before(start_paragraph)
        marker_start.add_run(f"[Locked Region Start] {region['id']}")
        marker_end = insert_paragraph_after(end_paragraph)
        marker_end.add_run(f"[Locked Region End] {region['id']}")

    for region in plan.get("regions", {}).get("fillable", []):
        start = region.get("start_paragraph")
        end = region.get("end_paragraph")
        if start is None or end is None or start >= len(original_paragraphs):
            continue
        start_paragraph = original_paragraphs[start]
        end_index = min(end, len(original_paragraphs) - 1)
        end_paragraph = original_paragraphs[end_index]
        marker_start = insert_paragraph_before(start_paragraph)
        marker_start.add_run(f"[Fillable Region Start] {region['id']}")
        clear_paragraph(start_paragraph)
        start_paragraph.add_run(f"【Preview Placeholder: {region['id']}】")
        for idx in range(start + 1, min(end + 1, len(original_paragraphs))):
            clear_paragraph(original_paragraphs[idx])
        marker_end = insert_paragraph_after(end_paragraph)
        marker_end.add_run(f"[Fillable Region End] {region['id']}")
    doc.save(preview_path)

    preview_relative = normalize_repo_relative(str(plan["selection"]["preview_output"]))
    summary_relative = preview_relative.removesuffix(".docx") + ".summary.json"
    summary = build_summary(
        plan,
        binding,
        summary_relative,
        preview_relative,
        template_recommendation,
    )
    dump_json(summary_path, summary)
    emit_json({"preview": str(preview_path), "summary": str(summary_path)})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
