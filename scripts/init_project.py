from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts._shared import (
    PROJECT_ROOT,
    dump_json,
    emit_json,
    ensure_text_file,
    import_docx,
    run_python_script,
)
from scripts._task_contract import default_task_contract, dump_task_contract


DEFAULT_DIRS = [
    "user",
    "templates",
    "config",
    "src",
    "tests",
    "assets/input",
    "assets/generated",
    "docs",
    "out",
    "logs",
    "temp",
]

TASK_REQUIREMENTS_STUB = """# Task Requirements

- 题目：
- 问题要求：
- 评分点：
- 其他硬性约束：
"""

DOCUMENT_REQUIREMENTS_STUB = """# Document Requirements

- 必需模块：
- 版式 / 设计要求：
- 是否需要目录：
- 是否需要参考文献：
- 其他结构要求：
"""


def ensure_sample_template(
    path: Path, *, reference: bool = False, overwrite: bool = False
) -> bool:
    if path.exists() and not overwrite:
        return False

    default_asset = (
        PROJECT_ROOT
        / "templates"
        / ("reference.sample.docx" if reference else "template.sample.docx")
    )
    if default_asset.exists():
        if path.exists() and path.resolve() == default_asset.resolve():
            return False
        path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(default_asset, path)
        return True

    docx = import_docx()
    text_module = __import__("docx.enum.text", fromlist=["WD_ALIGN_PARAGRAPH"])
    shared_module = __import__("docx.shared", fromlist=["Pt"])
    WD_ALIGN_PARAGRAPH = text_module.WD_ALIGN_PARAGRAPH
    Pt = shared_module.Pt

    doc = docx.Document()
    title = doc.add_paragraph()
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    title_run = title.add_run("Project Report Template")
    title_run.bold = True
    title_run.font.size = Pt(18)

    cover_lines = ["姓 名：", "学 号：", "完成日期："]
    if reference:
        cover_lines.append("模板角色：参考样式")

    for line in cover_lines:
        paragraph = doc.add_paragraph(line)
        paragraph.paragraph_format.space_after = Pt(6)

    doc.add_page_break()
    doc.add_heading("1 Overview", level=1)
    doc.add_paragraph("[Replace this section with project-specific body content.]")
    doc.add_heading("2 Details", level=1)
    doc.add_paragraph("[Add figures, tables, analysis, and references here.]")
    doc.add_heading("3 References", level=1)
    doc.add_paragraph("[Reference placeholder]")

    path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(path)
    return True


def copy_if_missing(src: Path | None, dst: Path, *, overwrite: bool = False) -> bool:
    if src is None or not src.exists() or (dst.exists() and not overwrite):
        return False
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    return True


def sync_script_skeleton(target_root: Path, *, overwrite: bool = False) -> list[str]:
    scripts_root = target_root / "scripts"
    scripts_root.mkdir(parents=True, exist_ok=True)
    copied: list[str] = []
    if target_root == PROJECT_ROOT:
        return copied

    for source in (PROJECT_ROOT / "scripts").glob("*.py"):
        destination = scripts_root / source.name
        if destination.exists() and not overwrite:
            continue
        shutil.copy2(source, destination)
        copied.append(str(destination))
    return copied


def sync_user_profile_language(
    user_profile_text: str, workflow_text: str, *, default_language: str = "zh-CN"
) -> str:
    language = default_language
    try:
        workflow = json.loads(workflow_text)
    except json.JSONDecodeError:
        workflow = {}

    language = workflow.get("project", {}).get("language") or default_language
    preference_line = f"- 语言偏好：{language}"
    lines = user_profile_text.splitlines()
    preserved_trailing_newline = user_profile_text.endswith("\n")

    for index, line in enumerate(lines):
        if line.startswith("- 语言偏好："):
            lines[index] = preference_line
            break
    else:
        insert_at = None
        for index, line in enumerate(lines):
            if line.strip() == "## Defaults":
                insert_at = index + 1
                while insert_at < len(lines) and lines[insert_at].startswith("- "):
                    insert_at += 1
                break

        if insert_at is None:
            lines.append("")
            lines.append("## Defaults")
            lines.append(preference_line)
        else:
            lines.insert(insert_at, preference_line)

    content = "\n".join(lines)
    if preserved_trailing_newline:
        content += "\n"
    return content


def sync_user_profile_bibliography_source(user_profile_text: str) -> str:
    placeholder = (
        "- 参考文献来源：needs_confirmation "
        "(agent_generate_verified_only | agent_search_and_screen | user_supplied_files)"
    )
    lines = user_profile_text.splitlines()
    preserved_trailing_newline = user_profile_text.endswith("\n")

    for index, line in enumerate(lines):
        if line.startswith("- 参考文献来源："):
            lines[index] = placeholder
            break
    else:
        insert_at = None
        for index, line in enumerate(lines):
            if line.strip() == "## Defaults":
                insert_at = index + 1
                while insert_at < len(lines) and lines[insert_at].startswith("- "):
                    insert_at += 1
                break
        if insert_at is None:
            lines.append("")
            lines.append("## Defaults")
            lines.append(placeholder)
        else:
            lines.insert(insert_at, placeholder)

    content = "\n".join(lines)
    if preserved_trailing_newline:
        content += "\n"
    return content


def default_file_templates() -> dict[str, str]:
    workflow_text = (PROJECT_ROOT / "workflow.json").read_text(encoding="utf-8")
    user_profile_text = (PROJECT_ROOT / "user" / "user.md").read_text(
        encoding="utf-8"
    )
    return {
        "workflow.json": workflow_text,
        "config/template.plan.json": (
            PROJECT_ROOT / "config" / "template.plan.json"
        ).read_text(encoding="utf-8"),
        "config/field.binding.json": (
            PROJECT_ROOT / "config" / "field.binding.json"
        ).read_text(encoding="utf-8"),
        "config/code-theme.user.sample.json": (
            PROJECT_ROOT / "config" / "code-theme.user.sample.json"
        ).read_text(encoding="utf-8"),
        "user/user.md": sync_user_profile_bibliography_source(
            sync_user_profile_language(user_profile_text, workflow_text)
        ),
        "user/soul.md": (PROJECT_ROOT / "user" / "soul.md").read_text(encoding="utf-8"),
        "docs/report_body.md": (PROJECT_ROOT / "docs" / "report_body.md").read_text(
            encoding="utf-8"
        ),
        "docs/task_requirements.md": TASK_REQUIREMENTS_STUB,
        "docs/document_requirements.md": DOCUMENT_REQUIREMENTS_STUB,
    }


def run_optional(script_name: str, project_root: Path) -> dict[str, object]:
    script = project_root / "scripts" / script_name
    if not script.exists():
        return {"script": script_name, "status": "skipped"}
    result = run_python_script(script, "--project-root", str(project_root))
    return {
        "script": script_name,
        "status": "ok" if result["returncode"] == 0 else "error",
        "returncode": result["returncode"],
        "stdout": result["stdout"],
        "stderr": result["stderr"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Initialize a report workflow project."
    )
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--template")
    parser.add_argument("--reference-template")
    parser.add_argument("--sample-template")
    parser.add_argument("--sample-reference")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    root = Path(args.project_root).resolve()
    created_dirs = []
    created_files = []
    for relative in DEFAULT_DIRS:
        path = root / relative
        if not path.exists():
            path.mkdir(parents=True, exist_ok=True)
            created_dirs.append(str(path))

    for relative, content in default_file_templates().items():
        if ensure_text_file(root / relative, content, overwrite=args.force):
            created_files.append(str(root / relative))

    task_contract_path = root / "report.task.yaml"
    if args.force or not task_contract_path.exists():
        dump_task_contract(task_contract_path, default_task_contract())
        created_files.append(str(task_contract_path))

    created_files.extend(sync_script_skeleton(root, overwrite=args.force))

    template_user = root / "templates" / "template.user.docx"
    reference_user = root / "templates" / "reference.user.docx"
    template_sample = root / "templates" / "template.sample.docx"
    reference_sample = root / "templates" / "reference.sample.docx"

    copied_templates = []
    if ensure_sample_template(template_sample, overwrite=args.force):
        copied_templates.append(str(template_sample))
    if ensure_sample_template(reference_sample, reference=True, overwrite=args.force):
        copied_templates.append(str(reference_sample))
    if copy_if_missing(
        Path(args.sample_template).resolve() if args.sample_template else None,
        template_sample,
        overwrite=args.force,
    ):
        copied_templates.append(str(template_sample))
    if copy_if_missing(
        Path(args.sample_reference).resolve() if args.sample_reference else None,
        reference_sample,
        overwrite=args.force,
    ):
        copied_templates.append(str(reference_sample))
    if copy_if_missing(
        Path(args.template).resolve()
        if args.template
        else template_sample
        if template_sample.exists()
        else None,
        template_user,
        overwrite=args.force,
    ):
        copied_templates.append(str(template_user))
    if copy_if_missing(
        Path(args.reference_template).resolve()
        if args.reference_template
        else reference_sample
        if reference_sample.exists()
        else None,
        reference_user,
        overwrite=args.force,
    ):
        copied_templates.append(str(reference_user))

    script_results = [run_optional("list_private_fields.py", root)]
    if template_user.exists():
        script_results.append(run_optional("scan_template.py", root))
        script_results.append(run_optional("recommend_template_styles.py", root))
        script_results.append(run_optional("build_preview.py", root))

    init_report = {
        "initialized": True,
        "created_dirs": created_dirs,
        "created_files": created_files,
        "copied_templates": copied_templates,
        "script_results": script_results,
        "next_actions": [
            "confirm preview",
            "confirm locked regions",
            "confirm field bindings",
        ],
    }
    dump_json(root / "logs" / "init_report.json", init_report)
    emit_json(init_report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
