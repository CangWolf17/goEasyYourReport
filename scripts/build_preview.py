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
from scripts._report_render import render_blocks
from scripts._preview_pairing import (
    build_pairing,
    file_fingerprint,
    normalize_repo_relative,
    recommendation_fingerprint,
)
from scripts._semantic_preview import build_semantic_preview
from scripts._shared import dump_json, emit_json, import_docx, load_json, project_path
from scripts._task_contract import load_task_contract


def representative_preview_blocks() -> list[dict[str, object]]:
    return [
        {
            "kind": "paragraph",
            "text": "这是用于确认模板正文、列表和表格样式的预览段落。",
        },
        {"kind": "heading", "level": 1, "text": "样式预览：一级标题"},
        {"kind": "heading", "level": 2, "text": "样式预览：二级标题"},
        {"kind": "list_item", "ordered": True, "depth": 0, "text": "编号列表示例"},
        {"kind": "list_item", "ordered": False, "depth": 0, "text": "符号列表示例"},
        {"kind": "table", "rows": [["列A", "列B"], ["示例1", "示例2"]]},
    ]


def paragraph_index(doc, target_paragraph) -> int:
    for index, paragraph in enumerate(doc.paragraphs):
        if paragraph._p is target_paragraph._p:
            return index
    raise ValueError("Paragraph not found in current document")


def inject_representative_preview_content(
    doc,
    *,
    start_paragraph,
    project_root: str,
    semantics: dict[str, object] | None,
) -> None:
    preview_anchor = insert_paragraph_after(start_paragraph)
    clear_paragraph(preview_anchor)
    anchor_index = paragraph_index(doc, preview_anchor)
    render_blocks(
        doc,
        {"start_paragraph": anchor_index, "end_paragraph": anchor_index},
        representative_preview_blocks(),
        Path(project_root).resolve(),
        Path(project_root).resolve(),
        {"name": "preview-style-sample", "warnings": [], "override_used": False},
        {
            "styled": 0,
            "highlighted": 0,
            "unsupported": [],
            "warnings": [],
            "theme": {"name": "preview-style-sample", "override_used": False},
        },
        semantics,
        {"unsupported": []},
    )


def build_summary(
    plan: dict[str, object],
    binding: dict[str, object],
    summary_relative: str,
    preview_relative: str,
    task_contract: dict[str, object],
    template_recommendation: dict[str, object] | None = None,
    pairing: dict[str, object] | None = None,
    semantic_preview: dict[str, object] | None = None,
) -> dict[str, object]:
    anchors = plan.get("anchors", {})
    if not isinstance(anchors, dict):
        anchors = {}

    bindings = binding.get("bindings", [])
    fields = binding.get("fields", [])
    availability = binding.get("availability", {})
    if not isinstance(bindings, list):
        bindings = []
    if not isinstance(fields, list):
        fields = []
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
    report_decisions = task_contract.get("decisions", {})
    field_candidates = anchors.get("field_candidates", [])
    locked_regions = plan.get("regions", {}).get("locked", [])
    if not isinstance(field_candidates, list):
        field_candidates = []
    if not isinstance(locked_regions, list):
        locked_regions = []
    cover_region_present = any(
        isinstance(region, dict) and region.get("id") == "cover"
        for region in locked_regions
    )
    body_only_profile = (
        isinstance(report_decisions, dict)
        and report_decisions.get("report_profile") == "body_only"
    )
    bound_anchor_texts = {
        str(item.get("anchor_text", "")).strip()
        for item in bindings
        if isinstance(item, dict) and str(item.get("anchor_text", "")).strip()
    }
    unbound_candidates = [
        str(item.get("text", "")).strip()
        for item in field_candidates
        if isinstance(item, dict)
        and str(item.get("text", "")).strip()
        and str(item.get("text", "")).strip() not in bound_anchor_texts
    ]
    private_template = {
        str(field["name"]): ""
        for field in fields
        if isinstance(field, dict)
        and field.get("source") == "private"
        and str(field.get("name", "")).strip()
    }

    blocking_confirmations: list[str] = []
    decision_required: list[str] = []
    advisory_warnings: list[str] = []
    if not plan.get("regions", {}).get("fillable", []):
        blocking_confirmations.append("no fillable regions detected")
    if not anchors.get("field_candidates", []):
        if cover_region_present and not body_only_profile:
            blocking_confirmations.append(
                "cover region detected without recognizable field candidates"
            )
        else:
            advisory_warnings.append("no field candidates detected")
    if not bindings:
        if cover_region_present and not body_only_profile:
            blocking_confirmations.append("no field bindings configured")
        else:
            advisory_warnings.append("no field bindings configured")
    if unbound_candidates:
        if body_only_profile:
            advisory_warnings.append("cover field candidates detected without bindings")
        else:
            blocking_confirmations.append(
                "cover field candidates detected without bindings"
            )
    if template_recommendation and template_recommendation.get("pending_acceptance"):
        decision_required.append("template style recommendation pending")
    if not outline_complete:
        decision_required.append("template outline semantics incomplete")
    if any(gap in {"列表编号", "列表符号"} for gap in style_gaps):
        decision_required.append("list style semantics unresolved")
    if toc.get("detected") and toc.get("needs_confirmation", False):
        blocking_confirmations.append("toc detected; confirm whether to enable")
    if cross_references.get("figure_table_enabled") == "needs_confirmation":
        decision_required.append(
            "confirm whether to insert figure/table cross references"
        )
    if (
        bibliography.get("output_block_present")
        and bibliography.get("source_mode") == "needs_confirmation"
    ):
        decision_required.append("confirm bibliography source mode")

    return {
        "version": "1.0",
        "template": plan["selection"]["primary_template"],
        "preview": preview_relative,
        "semantic_preview": semantic_preview or {},
        "summary": summary_relative,
        "task_contract": {
            "stage": task_contract["task"]["stage"],
            "ready_to_write": task_contract["task"]["ready_to_write"],
            "next_step": task_contract["runtime"]["next_step"],
            "preview_review_status": task_contract["runtime"].get(
                "preview_review_status", "unknown"
            ),
            "acceptance_status": task_contract["runtime"].get(
                "acceptance_status", "unknown"
            ),
        },
        "report_decisions": task_contract.get("decisions", {}),
        "regions": plan.get("regions", {}),
        "anchors": anchors,
        "field_binding": {
            "path": plan["field_binding"]["path"],
            "bindings": bindings,
            "availability": availability,
            "private_template": private_template,
            "unbound_candidates": unbound_candidates,
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
        "pairing": pairing or {},
        "review": {
            "warnings": advisory_warnings,
            "decision_required": decision_required,
            "blocking": blocking_confirmations,
            "needs_confirmation": blocking_confirmations + decision_required,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build a preview DOCX with fillable regions replaced by placeholders."
    )
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--plan", default="config/template.plan.json")
    parser.add_argument("--preview-output")
    args = parser.parse_args()

    plan = load_json(project_path(args.project_root, args.plan))
    template_path = project_path(
        args.project_root, plan["selection"]["primary_template"].replace("./", "")
    )
    preview_output = args.preview_output or plan["selection"]["preview_output"]
    preview_path = project_path(args.project_root, str(preview_output).replace("./", ""))
    summary_path = preview_path.with_suffix(".summary.json")
    binding_path = project_path(
        args.project_root, plan["field_binding"]["path"].replace("./", "")
    )

    if not template_path.exists():
        raise SystemExit(f"Template not found: {template_path}")
    if not binding_path.exists():
        raise SystemExit(f"Field binding not found: {binding_path}")

    binding = load_json(binding_path)
    task_contract = load_task_contract(project_path(args.project_root, "report.task.yaml"))
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
        inject_representative_preview_content(
            doc,
            start_paragraph=start_paragraph,
            project_root=args.project_root,
            semantics=plan.get("semantics"),
        )
    doc.save(preview_path)

    preview_relative = normalize_repo_relative(str(plan["selection"]["preview_output"]))
    if args.preview_output:
        preview_relative = normalize_repo_relative(str(args.preview_output))
    summary_relative = preview_relative.removesuffix(".docx") + ".summary.json"
    template_path = project_path(
        args.project_root, plan["selection"]["primary_template"].replace("./", "")
    )
    recommendation_relative = "./logs/template_style_recommendation.json"
    pairing = None
    if template_recommendation:
        pairing = build_pairing(
            Path(args.project_root).resolve(),
            template_path=plan["selection"]["primary_template"],
            template_fingerprint=file_fingerprint(template_path),
            recommendation_fingerprint_value=recommendation_fingerprint(
                template_recommendation
            ),
            recommended_template_path=template_recommendation.get("recommended_template"),
            preview_path=preview_relative,
            preview_summary_path=summary_relative,
            recommendation_path=recommendation_relative,
        )
        template_recommendation["pairing"] = pairing
        if recommendation_path.exists():
            dump_json(recommendation_path, template_recommendation)
    summary = build_summary(
        plan,
        binding,
        summary_relative,
        preview_relative,
        task_contract,
        template_recommendation,
        pairing,
        build_semantic_preview(Path(args.project_root).resolve(), plan),
    )
    dump_json(summary_path, summary)
    emit_json(
        {
            "preview": str(preview_path),
            "summary": str(summary_path),
            "semantic_preview": summary["semantic_preview"]["path"],
        }
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
