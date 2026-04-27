from __future__ import annotations

import hashlib
import shutil
from pathlib import Path
from typing import Any

from scripts._preview_pairing import file_fingerprint, normalize_repo_relative
from scripts._report_markdown import markdown_to_blocks
from scripts._report_render import load_code_block_theme, render_blocks
from scripts._shared import import_docx, project_path


SEMANTIC_PREVIEW_OUTPUT = "./out/semantic-preview.docx"
SEMANTIC_PREVIEW_BODY = "./temp/semantic-preview-body.md"


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def _bullet_lines(path: Path) -> list[str]:
    lines: list[str] = []
    for raw_line in _read_text(path).splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("- "):
            line = line[2:].strip()
        lines.append(line)
    return [line for line in lines if line]


def _fingerprint_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _needs_scaffold(body_text: str) -> bool:
    non_empty = [line.strip() for line in body_text.splitlines() if line.strip()]
    has_heading = any(line.lstrip().startswith("#") for line in non_empty)
    return len(non_empty) < 4 or not has_heading


def _build_scaffold_text(
    body_text: str,
    task_points: list[str],
    document_points: list[str],
) -> str:
    scaffold_lines = ["# 语义预览文档", ""]
    if body_text:
        scaffold_lines.extend(["## 当前正文草稿", "", body_text, ""])

    scaffold_lines.extend(
        [
            "## 一级结构预览",
            "",
            "### 任务要求待落实",
            "",
            *[f"- {item}" for item in task_points],
            "",
            "### 文档要求待落实",
            "",
            *[f"- {item}" for item in document_points],
            "",
            "## 待补充章节",
            "",
            "- 请按一级标题样式补充最终章节结构。",
            "- 请把尚未完成的问题、分析与结论直接写入对应章节。",
            "",
        ]
    )
    return "\n".join(scaffold_lines).strip() + "\n"


def semantic_preview_basis(project_root: Path) -> dict[str, Any]:
    body_path = project_root / "docs" / "report_body.md"
    task_requirements_path = project_root / "docs" / "task_requirements.md"
    document_requirements_path = project_root / "docs" / "document_requirements.md"

    body_text = _read_text(body_path).strip()
    body_fingerprint = (
        file_fingerprint(body_path) if body_path.exists() else _fingerprint_text("")
    )
    if not _needs_scaffold(body_text):
        return {
            "render_input_path": body_path,
            "render_input_relative": "./docs/report_body.md",
            "render_input_fingerprint": body_fingerprint,
            "source_path": "./docs/report_body.md",
            "source_fingerprint": body_fingerprint,
            "scaffold_mode": "source",
        }

    task_points = _bullet_lines(task_requirements_path) or ["请补充任务要求与评分关注点。"]
    document_points = _bullet_lines(document_requirements_path) or ["请补充文档结构、版式与输出要求。"]
    scaffold_text = _build_scaffold_text(body_text, task_points, document_points)
    return {
        "render_input_relative": SEMANTIC_PREVIEW_BODY,
        "render_input_fingerprint": _fingerprint_text(scaffold_text),
        "source_path": "./docs/report_body.md",
        "source_fingerprint": body_fingerprint,
        "scaffold_mode": "generated",
        "render_input_text": scaffold_text,
    }


def semantic_preview_basis_fingerprint(project_root: Path) -> str:
    basis = semantic_preview_basis(project_root)
    return str(basis["render_input_fingerprint"])


def assemble_semantic_preview_body(project_root: Path) -> dict[str, Any]:
    body_info = semantic_preview_basis(project_root)
    if body_info["scaffold_mode"] == "source":
        return body_info

    assembled_path = project_path(project_root, SEMANTIC_PREVIEW_BODY.replace("./", ""))
    assembled_path.parent.mkdir(parents=True, exist_ok=True)
    assembled_path.write_text(str(body_info.pop("render_input_text")), encoding="utf-8")
    body_info["render_input_path"] = assembled_path
    return body_info


def build_semantic_preview(
    project_root: Path,
    plan: dict[str, Any],
    *,
    output_relative: str = SEMANTIC_PREVIEW_OUTPUT,
) -> dict[str, Any]:
    template_relative = str(plan["selection"]["primary_template"])
    template_path = project_path(project_root, template_relative.replace("./", ""))
    preview_path = project_path(project_root, output_relative.replace("./", ""))
    preview_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(template_path, preview_path)

    body_info = assemble_semantic_preview_body(project_root)
    blocks = markdown_to_blocks(body_info["render_input_path"])
    docx = import_docx()
    doc = docx.Document(preview_path)

    fillable = plan.get("regions", {}).get("fillable", [])
    target_region = fillable[0] if fillable else {"start_paragraph": len(doc.paragraphs) - 1, "end_paragraph": len(doc.paragraphs) - 1}
    code_theme = load_code_block_theme(str(project_root))
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

    render_blocks(
        doc,
        target_region,
        blocks,
        body_info["render_input_path"].parent,
        Path(project_root).resolve(),
        code_theme,
        code_status,
        plan.get("semantics"),
        equation_status,
    )
    doc.save(preview_path)
    return {
        "path": normalize_repo_relative(output_relative),
        "source_path": body_info["source_path"],
        "render_input_path": body_info["render_input_relative"],
        "source_fingerprint": body_info["source_fingerprint"],
        "render_input_fingerprint": body_info["render_input_fingerprint"],
        "scaffold_mode": body_info["scaffold_mode"],
        "code_blocks": code_status,
        "equations": equation_status,
    }
