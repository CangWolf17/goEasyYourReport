from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

from scripts._shared import dump_json, dump_yaml, load_json, load_yaml
from scripts._workflow_state import default_runtime_state


DEFAULT_PRIMARY_TEMPLATE = "./templates/template.user.docx"


def default_task_contract() -> dict[str, object]:
    engine_runtime = default_runtime_state()
    return {
        "schema": {
            "kind": "report_task",
            "version": 1,
        },
        "task": {
            "stage": "collecting_materials",
            "ready_to_write": False,
            "needs_user_input": True,
        },
        "requirements": {
            "summary": "",
            "task_requirements_path": "./docs/task_requirements.md",
            "document_requirements_path": "./docs/document_requirements.md",
        },
        "inputs": {
            "template_path": DEFAULT_PRIMARY_TEMPLATE,
            "references_dir": "./docs/references",
            "assets_dir": "./assets/input",
            "evidence_dir": "./materials/evidence",
        },
        "decisions": {
            "report_profile": "standard",
            "toc_enabled": None,
            "references_required": None,
            "appendix_enabled": None,
            "agent_may_write_explanatory_text": True,
            "default_template_protected": True,
        },
        "runtime": {
            "workflow_config": "./workflow.json",
            "template_plan": "./config/template.plan.json",
            "field_binding": "./config/field.binding.json",
            "preview_output": "./out/preview.docx",
            "semantic_preview_output": "./out/semantic-preview.docx",
            "preview_review": "",
            "preview_review_status": "unknown",
            "preview_review_basis": {},
            "redacted_verify": "",
            "redacted_verify_status": "unknown",
            "redacted_verify_fingerprint": "",
            "acceptance_review": "",
            "acceptance_status": "unknown",
            "accepted_redacted_fingerprint": "",
            "retry_exhaustion": {"status": "clear", "count": 0},
            "handoff_status": "",
            "post_inject_check": {},
            "next_step": engine_runtime.pop("next_step", "prepare"),
            "current_step": engine_runtime.pop("current_step", "prepare"),
            "last_result": engine_runtime.pop("last_result", ""),
            "active_blockers": engine_runtime.pop("active_blockers", []),
            "artifacts": engine_runtime.pop("artifacts", {}),
            "approvals": engine_runtime.pop("approvals", {}),
            "retries": engine_runtime.pop("retries", {}),
            "handoff": engine_runtime.pop("handoff", {}),
        },
    }


def _merge_missing(defaults: dict[str, object], payload: dict[str, object]) -> dict[str, object]:
    merged: dict[str, object] = deepcopy(defaults)
    for key, value in payload.items():
        default_value = merged.get(key)
        if isinstance(default_value, dict) and isinstance(value, dict):
            merged[key] = _merge_missing(default_value, value)
        else:
            merged[key] = value
    return merged


def ensure_task_contract_shape(payload: dict[str, object]) -> dict[str, object]:
    if not isinstance(payload, dict):
        return default_task_contract()
    return _merge_missing(default_task_contract(), payload)


def load_task_contract(path: Path) -> dict[str, object]:
    if not path.exists():
        return default_task_contract()
    payload = load_yaml(path)
    if not isinstance(payload, dict):
        return default_task_contract()
    return ensure_task_contract_shape(payload)


def dump_task_contract(path: Path, payload: dict[str, Any]) -> None:
    dump_yaml(path, ensure_task_contract_shape(payload))


def resolve_primary_template(project_root: Path) -> str:
    plan_path = project_root / "config" / "template.plan.json"
    if not plan_path.exists():
        return DEFAULT_PRIMARY_TEMPLATE
    plan = load_json(plan_path)
    selection = plan.get("selection", {})
    if not isinstance(selection, dict):
        return DEFAULT_PRIMARY_TEMPLATE
    value = selection.get("primary_template")
    return str(value).strip() if value else DEFAULT_PRIMARY_TEMPLATE


def sync_template_authority_mirrors(project_root: Path) -> str:
    primary_template = resolve_primary_template(project_root)

    workflow_path = project_root / "workflow.json"
    if workflow_path.exists():
        workflow = load_json(workflow_path)
        templates = workflow.setdefault("templates", {})
        if isinstance(templates, dict) and templates.get("main_template") != primary_template:
            templates["main_template"] = primary_template
            dump_json(workflow_path, workflow)

    task_path = project_root / "report.task.yaml"
    task_contract = load_task_contract(task_path)
    inputs = task_contract.setdefault("inputs", {})
    if isinstance(inputs, dict) and inputs.get("template_path") != primary_template:
        inputs["template_path"] = primary_template
        dump_task_contract(task_path, task_contract)

    return primary_template
