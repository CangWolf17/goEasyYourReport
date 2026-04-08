from __future__ import annotations

import argparse
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts._shared import emit_json, import_docx, load_json, project_path


def paragraph_texts(doc):
    return [p.text.strip() for p in doc.paragraphs]


def verify_preview(plan, docx_path):
    errors = []
    summary_path = docx_path.with_suffix(".summary.json")
    if not summary_path.exists():
        errors.append(f"missing preview summary: {summary_path}")

    summary = {}
    if not errors:
        summary = load_json(summary_path)
        if summary.get("regions") != plan.get("regions", {}):
            errors.append(
                "preview summary regions do not match the current template plan"
            )

    docx = import_docx()
    preview_doc = docx.Document(docx_path)
    texts = paragraph_texts(preview_doc)

    for region in plan.get("regions", {}).get("locked", []):
        region_id = region.get("id")
        if f"[Locked Region Start] {region_id}" not in texts:
            errors.append(f"missing locked-region start marker: {region_id}")
        if f"[Locked Region End] {region_id}" not in texts:
            errors.append(f"missing locked-region end marker: {region_id}")

    for region in plan.get("regions", {}).get("fillable", []):
        region_id = region.get("id")
        if f"[Fillable Region Start] {region_id}" not in texts:
            errors.append(f"missing fillable-region start marker: {region_id}")
        if f"[Fillable Region End] {region_id}" not in texts:
            errors.append(f"missing fillable-region end marker: {region_id}")
        if f"【Preview Placeholder: {region_id}】" not in texts:
            errors.append(f"missing preview placeholder: {region_id}")

    return {
        "ok": not errors,
        "mode": "preview",
        "checked": str(docx_path),
        "summary": str(summary_path),
        "errors": errors,
    }


def verify_redacted(plan, template_path, docx_path):
    docx = import_docx()
    template_doc = docx.Document(template_path)
    target_doc = docx.Document(docx_path)
    template_texts = paragraph_texts(template_doc)
    target_texts = paragraph_texts(target_doc)

    mismatches = []
    for region in plan.get("regions", {}).get("locked", []):
        start = region.get("start_paragraph")
        end = region.get("end_paragraph")
        if start is None or end is None:
            continue
        for idx in range(start, min(end + 1, len(template_texts), len(target_texts))):
            if template_texts[idx] != target_texts[idx]:
                mismatches.append(
                    {
                        "region": region["id"],
                        "paragraph": idx,
                        "template": template_texts[idx],
                        "target": target_texts[idx],
                    }
                )

    return {
        "ok": not mismatches,
        "mode": "redacted",
        "checked": str(docx_path),
        "locked_region_mismatches": mismatches,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify report outputs and locked-region preservation."
    )
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--plan", default="config/template.plan.json")
    parser.add_argument("--docx", default="out/redacted.docx")
    args = parser.parse_args()

    plan = load_json(project_path(args.project_root, args.plan))
    template_path = project_path(
        args.project_root, plan["selection"]["primary_template"].replace("./", "")
    )
    docx_path = project_path(args.project_root, args.docx)

    errors = []
    if not template_path.exists():
        errors.append(f"missing template: {template_path}")
    if not docx_path.exists():
        errors.append(f"missing report: {docx_path}")
    if errors:
        emit_json({"ok": False, "errors": errors})
        return 1

    preview_relative = plan["selection"].get("preview_output", "out/preview.docx")
    preview_path = project_path(
        args.project_root, str(preview_relative).replace("./", "")
    )
    if docx_path == preview_path:
        result = verify_preview(plan, docx_path)
    else:
        result = verify_redacted(plan, template_path, docx_path)

    emit_json(result)
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
