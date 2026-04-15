from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts._global_defaults import (
    default_global_defaults,
    export_global_defaults,
    global_defaults_path,
    import_global_defaults,
    load_global_defaults,
    save_global_defaults,
    seed_missing_project_defaults,
)
from scripts._preview_pairing import evaluate_preview_pair_state
from scripts._shared import dump_json, emit_json, load_json, project_path, run_python_script
from scripts._task_contract import (
    dump_task_contract,
    load_task_contract,
    sync_template_authority_mirrors,
)


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


def task_contract_path(project_root: Path) -> Path:
    return project_root / "report.task.yaml"


def summarize_task_contract(task_contract: dict[str, object]) -> dict[str, object]:
    task = task_contract.get("task", {})
    runtime = task_contract.get("runtime", {})
    return {
        "stage": task.get("stage"),
        "ready_to_write": task.get("ready_to_write"),
        "next_step": runtime.get("next_step"),
    }


def sync_preview_summary(project_root: Path, task_contract: dict[str, object]) -> None:
    summary_path = project_path(project_root, "out/preview.summary.json")
    if not summary_path.exists():
        return
    summary_payload = load_json(summary_path)
    summary_payload["task_contract"] = summarize_task_contract(task_contract)
    dump_json(summary_path, summary_payload)


def persist_task_contract(
    project_root: Path,
    *,
    stage: str | None = None,
    ready_to_write: bool | None = None,
    needs_user_input: bool | None = None,
    next_step: str | None = None,
    runtime_updates: dict[str, object] | None = None,
    sync_summary: bool = False,
) -> dict[str, object]:
    task_contract = load_task_contract(task_contract_path(project_root))
    task = task_contract.setdefault("task", {})
    runtime = task_contract.setdefault("runtime", {})

    if stage is not None:
        task["stage"] = stage
    if ready_to_write is not None:
        task["ready_to_write"] = ready_to_write
    if needs_user_input is not None:
        task["needs_user_input"] = needs_user_input
    if runtime_updates:
        runtime.update(runtime_updates)
    if next_step is not None:
        runtime["next_step"] = next_step

    dump_task_contract(task_contract_path(project_root), task_contract)
    if sync_summary:
        sync_preview_summary(project_root, task_contract)
    return task_contract


def sync_prepare_task_contract(
    project_root: Path, warnings: list[object]
) -> dict[str, object]:
    task_contract = load_task_contract(task_contract_path(project_root))
    ready_to_write = bool(task_contract.get("task", {}).get("ready_to_write", False))
    if warnings:
        stage = "awaiting_confirmation"
        needs_user_input = True
        next_step = "review_preview_summary"
    elif ready_to_write:
        stage = "ready_to_build"
        needs_user_input = False
        next_step = "build"
    else:
        stage = "collecting_materials"
        needs_user_input = True
        next_step = "resolve_report_task_gate"
    return persist_task_contract(
        project_root,
        stage=stage,
        needs_user_input=needs_user_input,
        next_step=next_step,
        runtime_updates={
            "preview_output": "./out/preview.docx",
            "template_plan": "./config/template.plan.json",
            "field_binding": "./config/field.binding.json",
        },
        sync_summary=True,
    )


def blocking_review_items(summary_payload: dict[str, object]) -> list[object]:
    review = summary_payload.get("review", {})
    if not isinstance(review, dict):
        return []
    blocking = review.get("blocking")
    if isinstance(blocking, list):
        return blocking
    needs_confirmation = review.get("needs_confirmation", [])
    return needs_confirmation if isinstance(needs_confirmation, list) else []


def advisory_review_warnings(summary_payload: dict[str, object]) -> list[object]:
    review = summary_payload.get("review", {})
    if not isinstance(review, dict):
        return []
    warnings = review.get("warnings", [])
    return warnings if isinstance(warnings, list) else []


def decision_review_items(summary_payload: dict[str, object]) -> list[object]:
    review = summary_payload.get("review", {})
    if not isinstance(review, dict):
        return []
    decisions = review.get("decision_required", [])
    return decisions if isinstance(decisions, list) else []


def should_enforce_preview_pair(summary_payload: dict[str, object]) -> bool:
    template_recommendation = summary_payload.get("template_recommendation", {})
    if isinstance(template_recommendation, dict) and (
        template_recommendation.get("pending_acceptance")
        or template_recommendation.get("recommended_template")
    ):
        return True
    decisions = decision_review_items(summary_payload)
    style_decisions = {
        "template style recommendation pending",
        "template outline semantics incomplete",
        "list style semantics unresolved",
    }
    return any(str(item) in style_decisions for item in decisions)


def preview_pair_state(summary_payload: dict[str, object], project_root: Path) -> dict[str, object]:
    recommendation_path = project_path(project_root, "logs/template_style_recommendation.json")
    recommendation_payload = (
        load_json(recommendation_path) if recommendation_path.exists() else None
    )
    if not should_enforce_preview_pair(summary_payload):
        return {
            "pair_state": "matched",
            "issue_kinds": [],
            "next_step": str(summary_payload.get("task_contract", {}).get("next_step", "")),
            "pairing": summary_payload.get("pairing"),
        }
    return evaluate_preview_pair_state(
        project_root,
        recommendation_payload=recommendation_payload,
        preview_summary=summary_payload,
    )


def preview_pair_issues(pair_state_payload: dict[str, object]) -> list[dict[str, object]]:
    return [
        {
            "kind": kind,
            "details": pair_state_payload.get("pairing")
            if kind == "missing_pairing_metadata"
            else pair_state_payload.get("mismatch_fields", [])
            if kind == "mismatched_preview_pair"
            else "preview/recommendation artifacts are stale or incomplete",
        }
        for kind in pair_state_payload.get("issue_kinds", [])
    ]


def report_profile(task_contract: dict[str, object]) -> str:
    decisions = task_contract.get("decisions", {})
    if not isinstance(decisions, dict):
        return "standard"
    value = decisions.get("report_profile")
    return str(value).strip() if value else "standard"


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
    for item in build_payload.get("equations", {}).get("unsupported", []):
        issues.append(
            {
                "kind": "unsupported_equation_syntax",
                "severity": item.get("severity", "handoff"),
                "latex": item.get("latex"),
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


def handle_defaults_onboard(
    project_root: Path,
    *,
    use_defaults: bool,
    customize: bool,
    source: str | None = None,
    target: str | None = None,
) -> tuple[int, dict[str, object]]:
    if not use_defaults and not customize:
        use_defaults = True

    init_args: list[str] = []
    if source:
        init_args.extend(["--template", source, "--reference-template", source])
    init_result = run_repo_script("init_project.py", project_root, *init_args)
    if init_result["returncode"] != 0:
        return error_from_script("defaults-onboard", "init_project.py", init_result)

    defaults_payload = default_global_defaults()
    if source:
        defaults_payload["templates"] = {
            "template_source": str(Path(source).resolve()),
            "reference_template_source": str(Path(source).resolve()),
        }

    artifacts: dict[str, object] = {}
    if customize:
        recommendation_result = run_repo_script("recommend_template_styles.py", project_root)
        if recommendation_result["returncode"] != 0:
            return error_from_script(
                "defaults-onboard", "recommend_template_styles.py", recommendation_result
            )
        preview_result = run_repo_script(
            "build_preview.py",
            project_root,
            "--preview-output",
            "out/defaults-preview.docx",
        )
        if preview_result["returncode"] != 0:
            return error_from_script("defaults-onboard", "build_preview.py", preview_result)
        defaults_preview = project_path(project_root, "out/defaults-preview.docx")
        defaults_summary = project_path(project_root, "out/defaults-preview.summary.json")
        if not defaults_preview.exists() or not defaults_summary.exists():
            return 2, response(
                "defaults-onboard",
                "error",
                "Defaults customization requires a generated DOCX preview",
                issues=[{"kind": "missing_defaults_preview", "details": "customize path did not generate defaults preview artifacts"}],
                next_step="inspect_defaults_preview_generation",
            )
        artifacts["defaults_preview"] = "./out/defaults-preview.docx"
        artifacts["defaults_preview_summary"] = "./out/defaults-preview.summary.json"
        defaults_payload["templates"] = {
            "template_source": str((project_root / "templates" / "template.user.docx").resolve()),
            "reference_template_source": str((project_root / "templates" / "reference.user.docx").resolve()),
        }

    destination = Path(target).resolve() if target else None
    saved_path = save_global_defaults(defaults_payload, destination)
    artifacts["global_defaults"] = str(saved_path)
    return 0, response(
        "defaults-onboard",
        "ok",
        "Global defaults configured" if use_defaults else "Customized global defaults configured",
        artifacts=artifacts,
        next_step="done",
    )


def handle_defaults_status(project_root: Path) -> tuple[int, dict[str, object]]:
    defaults_payload = load_global_defaults()
    defaults_path = None
    if defaults_payload is not None:
        defaults_path = str(global_defaults_path())
    return 0, response(
        "defaults-status",
        "ok",
        "Global defaults found" if defaults_payload else "Global defaults not configured",
        artifacts={
            "global_defaults_path": defaults_path or "",
            "global_defaults": defaults_payload or {},
        },
        next_step="defaults-onboard" if defaults_payload is None else "done",
    )


def handle_defaults_import(source: str) -> tuple[int, dict[str, object]]:
    saved_path = import_global_defaults(Path(source).resolve())
    return 0, response(
        "defaults-import",
        "ok",
        "Global defaults imported",
        artifacts={"global_defaults": str(saved_path)},
        next_step="done",
    )


def handle_defaults_export(target: str) -> tuple[int, dict[str, object]]:
    exported_path = export_global_defaults(Path(target).resolve())
    return 0, response(
        "defaults-export",
        "ok",
        "Global defaults exported",
        artifacts={"exported_defaults": str(exported_path)},
        next_step="done",
    )


def handle_prepare(project_root: Path) -> tuple[int, dict[str, object]]:
    workflow_path = project_path(project_root, "workflow.json")
    if not workflow_path.exists():
        init_result = run_repo_script("init_project.py", project_root)
        if init_result["returncode"] != 0:
            return error_from_script("prepare", "init_project.py", init_result)

    sync_template_authority_mirrors(project_root)
    task_contract = load_task_contract(task_contract_path(project_root))
    if seed_missing_project_defaults(project_root, task_contract=task_contract):
        dump_task_contract(task_contract_path(project_root), task_contract)
        sync_template_authority_mirrors(project_root)

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
    summary_payload = load_json(summary_path) if summary_path.exists() else {}
    task_contract = load_task_contract(task_contract_path(project_root))
    blocking = blocking_review_items(summary_payload)
    decisions = decision_review_items(summary_payload)
    warnings = advisory_review_warnings(summary_payload)
    pair_state_payload = preview_pair_state(summary_payload, project_root)
    profile = report_profile(task_contract)
    task_contract = sync_prepare_task_contract(project_root, blocking)
    summary = (
        "Project prepared in body_only profile; review blocking confirmations only"
        if profile == "body_only" and blocking
        else
        "Project prepared; review blocking confirmations in preview summary"
        if blocking
        else
        "Project prepared in body_only profile; cover-field noise is advisory"
        if profile == "body_only"
        else "Project prepared; review decision items in preview summary"
        if decisions
        else "Project prepared and current workflow state collected"
    )
    issues = [
        {
            "kind": "confirmation_required",
            "details": item,
        }
        for item in blocking
    ] + [
        {
            "kind": "decision_required",
            "details": item,
        }
        for item in decisions
    ]
    payload = response(
        "prepare",
        "ok"
        if pair_state_payload["pair_state"] == "matched"
        else "needs_user_confirmation"
        if pair_state_payload["pair_state"] in {"stale", "mismatched"}
        else "needs_agent_handoff"
        if pair_state_payload["pair_state"] == "missing"
        and should_enforce_preview_pair(summary_payload)
        else "ok",
        summary,
        artifacts={
            "workflow": "./workflow.json",
            "preview": repo_relative(project_root, preview_path),
            "preview_summary": repo_relative(project_root, summary_path),
            "private_fields": fields_result["json"],
            "template_recommendation": "./logs/template_style_recommendation.json"
            if project_path(project_root, "logs/template_style_recommendation.json").exists()
            else "",
            "pairing": pair_state_payload.get("pairing") or {},
            "pair_state": pair_state_payload["pair_state"],
        },
        issues=issues + preview_pair_issues(pair_state_payload),
        warnings=warnings,
        next_step=(
            "preview"
            if pair_state_payload["pair_state"] in {"stale", "mismatched", "missing"}
            and should_enforce_preview_pair(summary_payload)
            else str(task_contract["runtime"]["next_step"])
        ),
    )
    exit_code = 0 if payload["status"] == "ok" else 1 if payload["status"] == "needs_user_confirmation" else 2
    return exit_code, payload


def handle_bootstrap(project_root: Path) -> tuple[int, dict[str, object]]:
    workflow_existed = project_path(project_root, "workflow.json").exists()
    exit_code, payload = handle_prepare(project_root)
    payload["action"] = "bootstrap"
    if exit_code == 0:
        payload["summary"] = (
            "Project bootstrapped and prepared"
            if not workflow_existed
            else "Project already bootstrapped; current workflow state collected"
        )
    return exit_code, payload


def handle_ready(project_root: Path) -> tuple[int, dict[str, object]]:
    summary_path = project_path(project_root, "out/preview.summary.json")
    if not summary_path.exists():
        return 1, response(
            "ready",
            "needs_user_confirmation",
            "Ready gate requires a current preview summary",
            issues=[
                {
                    "kind": "missing_preview_summary",
                    "details": "run prepare or preview before marking ready_to_write",
                }
            ],
            next_step="prepare",
        )

    summary_payload = load_json(summary_path)
    pair_state_payload = preview_pair_state(summary_payload, project_root)
    task_contract = load_task_contract(task_contract_path(project_root))
    blocking = blocking_review_items(summary_payload)
    decisions = decision_review_items(summary_payload)
    warnings = advisory_review_warnings(summary_payload)
    profile = report_profile(task_contract)
    recommendation_pending = bool(
        isinstance(summary_payload.get("template_recommendation"), dict)
        and summary_payload["template_recommendation"].get("pending_acceptance")
    )
    if blocking or recommendation_pending or pair_state_payload["pair_state"] != "matched":
        task_contract = sync_prepare_task_contract(project_root, blocking)
        return 1, response(
            "ready",
            "needs_user_confirmation",
            "Ready gate blocked by unresolved confirmations"
            if blocking
            else "Ready gate blocked until recommendation and preview artifacts are current",
            artifacts={
                "preview_summary": "./out/preview.summary.json",
                "pairing": pair_state_payload.get("pairing") or {},
                "pair_state": pair_state_payload["pair_state"],
            },
            issues=[
                {
                    "kind": "confirmation_required",
                    "details": item,
                }
                for item in blocking
            ]
            + (
                [{"kind": "template_recommendation_pending", "details": "review preview and accept or reject the recommended template"}]
                if recommendation_pending
                else []
            )
            + preview_pair_issues(pair_state_payload),
            warnings=warnings,
            next_step="preview"
            if recommendation_pending or pair_state_payload["pair_state"] != "matched"
            else str(task_contract["runtime"]["next_step"]),
        )

    task_contract = persist_task_contract(
        project_root,
        stage="ready_to_build",
        ready_to_write=True,
        needs_user_input=False,
        next_step="build",
        sync_summary=True,
    )
    return 0, response(
        "ready",
        "ok",
        "Report task marked ready_to_write",
        artifacts={
            "preview_summary": "./out/preview.summary.json",
            "pairing": pair_state_payload.get("pairing") or {},
            "pair_state": pair_state_payload["pair_state"],
        },
        warnings=(
            (["body_only profile active; cover-field noise treated as advisory"] if profile == "body_only" else [])
            + warnings
        )
        + [f"decision required: {item}" for item in decisions],
        next_step=str(task_contract["runtime"]["next_step"]),
    )


def handle_status(project_root: Path) -> tuple[int, dict[str, object]]:
    task_contract = load_task_contract(task_contract_path(project_root))
    artifacts = {"task_contract": "./report.task.yaml"}
    summary_path = project_path(project_root, "out/preview.summary.json")
    if summary_path.exists():
        artifacts["preview_summary"] = "./out/preview.summary.json"
        summary_payload = load_json(summary_path)
        pair_state_payload = preview_pair_state(summary_payload, project_root)
        artifacts["pairing"] = pair_state_payload.get("pairing") or {}
        artifacts["pair_state"] = pair_state_payload["pair_state"]
        if project_path(project_root, "logs/template_style_recommendation.json").exists():
            artifacts["template_recommendation"] = "./logs/template_style_recommendation.json"
        blocking = blocking_review_items(summary_payload)
        decisions = decision_review_items(summary_payload)
        warnings = advisory_review_warnings(summary_payload)
        ready_to_write = bool(task_contract.get("task", {}).get("ready_to_write", False))
        profile = report_profile(task_contract)
        if ready_to_write and not blocking:
            summary = (
                "Workflow is ready_to_write; non-blocking decision items remain"
                if decisions
                else "Workflow is ready_to_write in body_only profile"
                if profile == "body_only"
                else "Workflow is ready_to_write and clear to build"
            )
        elif blocking:
            summary = "Workflow has blocking confirmations to review"
        elif decisions:
            summary = "Workflow has non-blocking decision items to review"
        elif profile == "body_only":
            summary = "Workflow is in body_only profile; no blocking confirmations"
        else:
            summary = "Workflow has no blocking confirmations"
        if pair_state_payload["pair_state"] in {"missing", "stale", "mismatched"}:
            summary = f"Workflow preview/recommendation pair is {pair_state_payload['pair_state']}; preview must be refreshed before ready"
        return 0, response(
            "status",
            "ok",
            summary,
            artifacts=artifacts,
            issues=[
                {
                    "kind": "confirmation_required",
                    "details": item,
                }
                for item in blocking
            ]
            + [
                {
                    "kind": "decision_required",
                    "details": item,
                }
                for item in decisions
            ]
            + preview_pair_issues(pair_state_payload),
            warnings=(
                (["body_only profile active; cover-field noise treated as advisory"] if profile == "body_only" else [])
                + warnings
            ),
            next_step="preview"
            if pair_state_payload["pair_state"] in {"missing", "stale", "mismatched"}
            and should_enforce_preview_pair(summary_payload)
            else str(task_contract.get("runtime", {}).get("next_step", "")),
        )

    return 0, response(
        "status",
        "ok",
        "Workflow status collected; no preview summary yet",
        artifacts=artifacts,
        warnings=["run prepare to generate preview.summary and confirmation details"],
        next_step=str(task_contract.get("runtime", {}).get("next_step", "")),
    )


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
    pair_state_payload = preview_pair_state(summary_payload, project_root)
    warnings = advisory_review_warnings(summary_payload)
    decisions = decision_review_items(summary_payload)
    needs_confirmation = blocking_review_items(summary_payload)
    if (
        verify_result["returncode"] == 0
        and not needs_confirmation
        and pair_state_payload["pair_state"] == "matched"
    ):
        task_contract = sync_prepare_task_contract(project_root, [])
        return 0, response(
            "preview",
            "ok",
            "Preview built and verified",
            artifacts={
                "preview": "./out/preview.docx",
                "preview_summary": "./out/preview.summary.json",
                "pairing": pair_state_payload.get("pairing") or {},
                "pair_state": pair_state_payload["pair_state"],
            },
            issues=[
                {
                    "kind": "decision_required",
                    "details": item,
                }
                for item in decisions
            ],
            warnings=warnings,
            next_step=str(task_contract["runtime"]["next_step"]),
        )

    if verify_result["returncode"] == 0:
        task_contract = sync_prepare_task_contract(project_root, needs_confirmation)
        return 1, response(
            "preview",
            "needs_user_confirmation",
            "Preview built; user confirmation is required",
            artifacts={
                "preview": "./out/preview.docx",
                "preview_summary": "./out/preview.summary.json",
                "pairing": pair_state_payload.get("pairing") or {},
                "pair_state": pair_state_payload["pair_state"],
            },
            issues=[
                {
                    "kind": "confirmation_required",
                    "details": item,
                }
                for item in needs_confirmation
            ]
            + preview_pair_issues(pair_state_payload),
            warnings=warnings,
            next_step="preview"
            if pair_state_payload["pair_state"] in {"missing", "stale", "mismatched"}
            else str(task_contract["runtime"]["next_step"]),
        )

    issues = verify_issue_list(verify_result["json"])
    task_contract = persist_task_contract(
        project_root,
        stage="collecting_materials",
        needs_user_input=False,
        next_step="fix_preview_verification",
        runtime_updates={
            "preview_output": "./out/preview.docx",
            "template_plan": "./config/template.plan.json",
            "field_binding": "./config/field.binding.json",
        },
        sync_summary=True,
    )
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
        next_step=str(task_contract["runtime"]["next_step"]),
    )


def handle_build(project_root: Path) -> tuple[int, dict[str, object]]:
    task_contract = load_task_contract(task_contract_path(project_root))
    task = task_contract.get("task", {})
    if not bool(task.get("ready_to_write", False)):
        task_contract = persist_task_contract(
            project_root,
            stage="collecting_materials",
            needs_user_input=True,
            next_step="resolve_report_task_gate",
            sync_summary=True,
        )
        return 1, response(
            "build",
            "needs_user_confirmation",
            "Build blocked until report task is ready_to_write",
            issues=[
                {
                    "kind": "not_ready_to_write",
                    "details": "report.task.yaml indicates materials or confirmations are incomplete",
                }
            ],
            next_step=str(task_contract["runtime"]["next_step"]),
        )

    plan_path = project_path(project_root, "config/template.plan.json")
    if plan_path.exists():
        plan = load_json(plan_path)
        semantics = plan.get("semantics", {})
        toc = semantics.get("toc", {}) if isinstance(semantics, dict) else {}
        if isinstance(toc, dict) and toc.get("detected") and toc.get(
            "needs_confirmation", False
        ):
            preview_result = run_repo_script("build_preview.py", project_root)
            if preview_result["returncode"] != 0:
                return error_from_script("build", "build_preview.py", preview_result)
            summary_path = project_path(project_root, "out/preview.summary.json")
            summary_payload = load_json(summary_path) if summary_path.exists() else {}
            review = summary_payload.get("review", {})
            needs_confirmation = (
                review.get("needs_confirmation", []) if isinstance(review, dict) else []
            )
            task_contract = sync_prepare_task_contract(project_root, needs_confirmation)
            return 1, response(
                "build",
                "needs_user_confirmation",
                "Build blocked until TOC confirmation is resolved",
                artifacts={
                    "preview": "./out/preview.docx",
                    "preview_summary": "./out/preview.summary.json",
                },
                next_step=str(task_contract["runtime"]["next_step"]),
            )

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

    task_contract = persist_task_contract(
        project_root,
        stage="redacted_built",
        needs_user_input=False,
        next_step="verify",
        runtime_updates={"redacted_output": "./out/redacted.docx"},
        sync_summary=True,
    )

    return 0, response(
        "build",
        "ok",
        "Redacted build completed successfully",
        artifacts=artifacts,
        warnings=warnings,
        next_step=str(task_contract["runtime"]["next_step"]),
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

    for action_name in ("bootstrap", "prepare", "ready", "status", "preview", "build"):
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

    defaults_onboard_parser = subparsers.add_parser("defaults-onboard")
    defaults_onboard_parser.add_argument("--project-root", default=".")
    defaults_onboard_parser.add_argument("--use-defaults", action="store_true")
    defaults_onboard_parser.add_argument("--customize", action="store_true")
    defaults_onboard_parser.add_argument("--source")
    defaults_onboard_parser.add_argument("--target")

    defaults_status_parser = subparsers.add_parser("defaults-status")
    defaults_status_parser.add_argument("--project-root", default=".")

    defaults_import_parser = subparsers.add_parser("defaults-import")
    defaults_import_parser.add_argument("--project-root", default=".")
    defaults_import_parser.add_argument("--source", required=True)

    defaults_export_parser = subparsers.add_parser("defaults-export")
    defaults_export_parser.add_argument("--project-root", default=".")
    defaults_export_parser.add_argument("--target", required=True)

    args = parser.parse_args()
    project_root = Path(getattr(args, "project_root", ".")).resolve()

    if args.action == "bootstrap":
        exit_code, payload = handle_bootstrap(project_root)
    elif args.action == "prepare":
        exit_code, payload = handle_prepare(project_root)
    elif args.action == "ready":
        exit_code, payload = handle_ready(project_root)
    elif args.action == "status":
        exit_code, payload = handle_status(project_root)
    elif args.action == "preview":
        exit_code, payload = handle_preview(project_root)
    elif args.action == "build":
        exit_code, payload = handle_build(project_root)
    elif args.action == "verify":
        exit_code, payload = handle_verify(project_root, args.target)
    elif args.action == "inject":
        exit_code, payload = handle_inject(project_root, args.source)
    elif args.action == "defaults-onboard":
        exit_code, payload = handle_defaults_onboard(
            project_root,
            use_defaults=args.use_defaults,
            customize=args.customize,
            source=args.source,
            target=args.target,
        )
    elif args.action == "defaults-status":
        exit_code, payload = handle_defaults_status(project_root)
    elif args.action == "defaults-import":
        exit_code, payload = handle_defaults_import(args.source)
    elif args.action == "defaults-export":
        exit_code, payload = handle_defaults_export(args.target)
    else:
        exit_code, payload = handle_cleanup(project_root, args.temp, args.logs)

    emit_json(payload)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
