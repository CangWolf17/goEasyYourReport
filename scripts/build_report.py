from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts._docx_integrity import validate_docx_package
from scripts._docx_postprocess import (
    apply_cross_reference_pass,
    apply_toc_if_enabled,
    append_bibliography_output,
    ensure_toc_styles,
    refresh_toc_with_word_if_available,
)
from scripts._report_markdown import markdown_to_blocks
from scripts._report_render import load_code_block_theme, render_blocks
from scripts._shared import emit_json, import_docx, load_json, project_path


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build a redacted report from the selected template and body source."
    )
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--plan", default="config/template.plan.json")
    args = parser.parse_args()

    plan = load_json(project_path(args.project_root, args.plan))
    template_path = project_path(
        args.project_root, plan["selection"]["primary_template"].replace("./", "")
    )
    redacted_path = project_path(
        args.project_root, plan["selection"]["redacted_output"].replace("./", "")
    )
    body_path = project_path(
        args.project_root, plan["body_source"]["path"].replace("./", "")
    )

    if not template_path.exists():
        raise SystemExit(f"Template not found: {template_path}")
    if not body_path.exists():
        raise SystemExit(f"Body source not found: {body_path}")

    shutil.copy2(template_path, redacted_path)
    docx = import_docx()
    doc = docx.Document(redacted_path)

    blocks = markdown_to_blocks(body_path)
    code_theme = load_code_block_theme(args.project_root)
    code_status: dict[str, object] = {
        "styled": 0,
        "highlighted": 0,
        "unsupported": [],
        "warnings": list(code_theme.get("warnings", [])),
        "theme": {
            "name": code_theme["name"],
            "override_used": bool(code_theme.get("override_used", False)),
        },
    }
    equation_status: dict[str, object] = {"unsupported": []}
    image_status = {"inserted": [], "normalized": [], "failed": []}
    fillable = plan.get("regions", {}).get("fillable", [])
    if fillable:
        image_status = render_blocks(
            doc,
            fillable[0],
            blocks,
            body_path.parent,
            Path(args.project_root).resolve(),
            code_theme,
            code_status,
            plan.get("semantics"),
            equation_status,
        )
    apply_toc_if_enabled(doc, plan)
    append_bibliography_output(doc, plan, args.project_root)
    apply_cross_reference_pass(doc, plan)
    doc.save(redacted_path)

    toc_refresh_status = {
        "attempted": bool(plan.get("semantics", {}).get("toc", {}).get("enabled")),
        "updated": False,
    }
    if toc_refresh_status["attempted"]:
        toc_refresh_status["updated"] = refresh_toc_with_word_if_available(
            redacted_path
        )
        if toc_refresh_status["updated"]:
            refreshed_doc = docx.Document(redacted_path)
            ensure_toc_styles(refreshed_doc)
            refreshed_doc.save(redacted_path)

    integrity_report = validate_docx_package(redacted_path)
    payload = {
        "redacted": str(redacted_path),
        "images": image_status,
        "code_blocks": code_status,
        "equations": equation_status,
        "toc_refresh": toc_refresh_status,
        "integrity": integrity_report,
    }
    if not integrity_report["ok"]:
        emit_json(payload)
        return 2

    emit_json(payload)
    return (
        1
        if image_status["failed"]
        or code_status["unsupported"]
        or equation_status["unsupported"]
        else 0
    )


if __name__ == "__main__":
    raise SystemExit(main())
