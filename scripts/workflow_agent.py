from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts._shared import emit_json, load_json, project_path, run_python_script


SCRIPT_ROOT = Path(__file__).resolve().parent


def repo_relative(project_root: Path, path_value: str | Path) -> str:
    path = Path(path_value)
    if not path.is_absolute():
        path = (project_root / path).resolve()
    else:
        path = path.resolve()
    try:
        relative = path.relative_to(project_root.resolve())
    except ValueError:
        return str(path)
    return f"./{relative.as_posix()}"


def response(
    action: str,
    status: str,
    summary: str,
    *,
    artifacts: dict[str, object] | None = None,
    issues: list[dict[str, object]] | None = None,
    warnings: list[object] | None = None,
    next_step: str = "",
) -> dict[str, object]:
    return {
        "action": action,
        "status": status,
        "summary": summary,
        "artifacts": artifacts or {},
        "issues": issues or [],
        "warnings": warnings or [],
        "next_step": next_step,
    }


def run_repo_script(
    script_name: str, project_root: Path, *extra_args: str
) -> dict[str, Any]:
    script_path = SCRIPT_ROOT / script_name
    if not script_path.exists():
        return {
            "returncode": 2,
            "stdout": "",
            "stderr": f"Missing script: {script_path}",
            "json": None,
            "json_error": None,
        }
    return run_python_script(
        script_path,
        "--project-root",
        str(project_root),
        *extra_args,
    )


def error_from_script(
    action: str,
    script_name: str,
    result: dict[str, Any],
) -> tuple[int, dict[str, object]]:
    details = result.get("stderr") or result.get("stdout") or "unknown script failure"
    return 2, response(
        action,
        "error",
        f"{script_name} failed",
        issues=[
            {
                "kind": "script_execution_failed",
                "script": script_name,
                "details": details,
            }
        ],
        next_step="inspect_script_failure",
    )


def build_issue_list(build_payload: dict[str, Any]) -> list[dict[str, object]]:
    issues: list[dict[str, object]] = []
    for item in build_payload.get("images", {}).get("failed", []):
        issues.append(
            {
                "kind": "image_insert_failed",
                "severity": "handoff",
                "path": item.get("path"),
                "reason": item.get("reason"),
                "agent_action": "review_or_fix_image_before_private_output",
            }
        )
    for item in build_payload.get("code_blocks", {}).get("unsupported", []):
        issues.append(
            {
                "kind": "unsupported_code_language",
                "severity": "handoff",
                "language": item.get("language"),
                "normalized": item.get("normalized"),
                "document_fallback": "styled_plain_code_block_rendered",
                "agent_action": "decide_with_user_before_private_output",
            }
        )
    return issues


def verify_issue_list(payload: dict[str, Any]) -> list[dict[str, object]]:
    issues: list[dict[str, object]] = []
    for error in payload.get("errors", []):
        issues.append(
            {
                "kind": "verification_error",
                "severity": "handoff",
                "details": error,
            }
        )
    for mismatch in payload.get("locked_region_mismatches", []):
        issues.append(
            {
                "kind": "locked_region_mismatch",
                "severity": "handoff",
                "region": mismatch.get("region"),
                "paragraph": mismatch.get("paragraph"),
            }
        )
    return issues


def handle_prepare(project_root: Path) -> tuple[int, dict[str, object]]:
    workflow_path = project_path(project_root, "workflow.json")
    if not workflow_path.exists():
        init_result = run_repo_script("init_project.py", project_root)
        if init_result["returncode"] != 0:
            return error_from_script("prepare", "init_project.py", init_result)

    fields_result = run_repo_script("list_private_fields.py", project_root)
    if fields_result["returncode"] != 0 or fields_result["json"] is None:
        return error_from_script("prepare", "list_private_fields.py", fields_result)

    for script_name in (
        "scan_template.py",
        "recommend_template_styles.py",
        "build_preview.py",
    ):
        result = run_repo_script(script_name, project_root)
        if result["returncode"] != 0:
            return error_from_script("prepare", script_name, result)

    preview_path = project_path(project_root, "out/preview.docx")
    summary_path = project_path(project_root, "out/preview.summary.json")
    payload = response(
        "prepare",
        "ok",
        "Project prepared and current workflow state collected",
        artifacts={
            "workflow": "./workflow.json",
            "preview": repo_relative(project_root, preview_path),
            "preview_summary": repo_relative(project_root, summary_path),
            "private_fields": fields_result["json"],
        },
        next_step="preview",
    )
    return 0, payload


def handle_preview(project_root: Path) -> tuple[int, dict[str, object]]:
    for script_name in (
        "scan_template.py",
        "recommend_template_styles.py",
        "build_preview.py",
    ):
        result = run_repo_script(script_name, project_root)
        if result["returncode"] != 0:
            return error_from_script("preview", script_name, result)

    verify_result = run_repo_script(
        "verify_report.py", project_root, "--docx", "out/preview.docx"
    )
    if verify_result["json"] is None:
        return error_from_script("preview", "verify_report.py", verify_result)

    summary_path = project_path(project_root, "out/preview.summary.json")
    summary_payload = load_json(summary_path) if summary_path.exists() else {}
    review = summary_payload.get("review", {})
    warnings = review.get("warnings", []) if isinstance(review, dict) else []
    needs_confirmation = (
        review.get("needs_confirmation", []) if isinstance(review, dict) else []
    )
    if verify_result["returncode"] == 0 and not needs_confirmation:
        return 0, response(
            "preview",
            "ok",
            "Preview built and verified",
            artifacts={
                "preview": "./out/preview.docx",
                "preview_summary": "./out/preview.summary.json",
            },
            warnings=warnings,
            next_step="build",
        )

    if verify_result["returncode"] == 0:
        return 1, response(
            "preview",
            "needs_user_confirmation",
            "Preview built; user confirmation is required",
            artifacts={
                "preview": "./out/preview.docx",
                "preview_summary": "./out/preview.summary.json",
            },
            warnings=warnings,
            next_step="review_preview_summary",
        )

    issues = verify_issue_list(verify_result["json"])
    return 1, response(
        "preview",
        "needs_agent_handoff",
        "Preview verification reported issues",
        artifacts={
            "preview": "./out/preview.docx",
            "preview_summary": "./out/preview.summary.json",
        },
        issues=issues,
        warnings=warnings,
        next_step="fix_preview_verification",
    )


def handle_build(project_root: Path) -> tuple[int, dict[str, object]]:
    result = run_repo_script("build_report.py", project_root)
    if result["json"] is None:
        return error_from_script("build", "build_report.py", result)

    payload = result["json"]
    artifacts = {
        "redacted": repo_relative(
            project_root, payload.get("redacted", "out/redacted.docx")
        )
    }
    integrity = payload.get("integrity", {})
    if isinstance(integrity, dict) and not integrity.get("ok", True):
        return 2, response(
            "build",
            "error",
            "Redacted build failed DOCX integrity validation",
            artifacts=artifacts,
            issues=[
                {
                    "kind": "docx_integrity_error",
                    "details": integrity.get("errors", []),
                }
            ],
            next_step="inspect_docx_integrity_errors",
        )

    issues = build_issue_list(payload)
    warnings = payload.get("code_blocks", {}).get("warnings", [])

    if issues:
        return 1, response(
            "build",
            "needs_agent_handoff",
            "Redacted build completed with issues that require review",
            artifacts=artifacts,
            issues=issues,
            warnings=warnings,
            next_step="review_build_issues",
        )

    if result["returncode"] != 0:
        return error_from_script("build", "build_report.py", result)

    return 0, response(
        "build",
        "ok",
        "Redacted build completed successfully",
        artifacts=artifacts,
        warnings=warnings,
        next_step="verify",
    )


def handle_verify(project_root: Path, target: str) -> tuple[int, dict[str, object]]:
    docx_arg = "out/preview.docx" if target == "preview" else "out/redacted.docx"
    result = run_repo_script("verify_report.py", project_root, "--docx", docx_arg)
    if result["json"] is None:
        return error_from_script("verify", "verify_report.py", result)

    payload = result["json"]
    artifacts = {"checked": repo_relative(project_root, docx_arg)}
    if payload.get("ok"):
        next_step = "build" if target == "preview" else "inject"
        return 0, response(
            "verify",
            "ok",
            f"{target} verification passed",
            artifacts=artifacts,
            next_step=next_step,
        )

    return 1, response(
        "verify",
        "needs_agent_handoff",
        f"{target} verification reported issues",
        artifacts=artifacts,
        issues=verify_issue_list(payload),
        next_step=f"fix_{target}_verification",
    )


def handle_inject(
    project_root: Path, source: str | None
) -> tuple[int, dict[str, object]]:
    extra_args: list[str] = []
    if source:
        extra_args.extend(["--source", source])
    result = run_repo_script("inject_private_fields.py", project_root, *extra_args)
    if result["json"] is None:
        return error_from_script("inject", "inject_private_fields.py", result)

    payload = result["json"]
    artifacts = {
        "private_output": repo_relative(
            project_root, payload.get("private_output", "out/private.docx")
        )
    }
    missing = payload.get("missing", [])
    if missing:
        return 1, response(
            "inject",
            "needs_agent_handoff",
            "Private injection finished with unresolved fields",
            artifacts=artifacts,
            issues=[
                {
                    "kind": "missing_private_fields",
                    "severity": "handoff",
                    "fields": missing,
                    "agent_action": "resolve_private_field_source",
                }
            ],
            next_step="resolve_private_fields",
        )

    return 0, response(
        "inject",
        "ok",
        "Private output generated successfully",
        artifacts=artifacts,
        next_step="done",
    )


def handle_cleanup(
    project_root: Path, temp: bool, logs: bool
) -> tuple[int, dict[str, object]]:
    if not temp and not logs:
        temp = True
        logs = True
    extra_args: list[str] = []
    if temp:
        extra_args.append("--temp")
    if logs:
        extra_args.append("--logs")
    result = run_repo_script("cleanup_project.py", project_root, *extra_args)
    if result["json"] is None or result["returncode"] != 0:
        return error_from_script("cleanup", "cleanup_project.py", result)

    return 0, response(
        "cleanup",
        "ok",
        "Cleanup completed",
        artifacts={"removed": result["json"].get("removed", [])},
        next_step="done",
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Stable agent-facing facade for the report workflow."
    )
    subparsers = parser.add_subparsers(dest="action", required=True)

    for action_name in ("prepare", "preview", "build"):
        action_parser = subparsers.add_parser(action_name)
        action_parser.add_argument("--project-root", default=".")

    verify_parser = subparsers.add_parser("verify")
    verify_parser.add_argument("--project-root", default=".")
    verify_parser.add_argument(
        "--target", choices=("preview", "redacted"), default="redacted"
    )

    inject_parser = subparsers.add_parser("inject")
    inject_parser.add_argument("--project-root", default=".")
    inject_parser.add_argument("--source")

    cleanup_parser = subparsers.add_parser("cleanup")
    cleanup_parser.add_argument("--project-root", default=".")
    cleanup_parser.add_argument("--temp", action="store_true")
    cleanup_parser.add_argument("--logs", action="store_true")

    args = parser.parse_args()
    project_root = Path(getattr(args, "project_root", ".")).resolve()

    if args.action == "prepare":
        exit_code, payload = handle_prepare(project_root)
    elif args.action == "preview":
        exit_code, payload = handle_preview(project_root)
    elif args.action == "build":
        exit_code, payload = handle_build(project_root)
    elif args.action == "verify":
        exit_code, payload = handle_verify(project_root, args.target)
    elif args.action == "inject":
        exit_code, payload = handle_inject(project_root, args.source)
    else:
        exit_code, payload = handle_cleanup(project_root, args.temp, args.logs)

    emit_json(payload)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
