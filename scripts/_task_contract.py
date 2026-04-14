from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

from scripts._shared import dump_yaml, load_yaml


def default_task_contract() -> dict[str, object]:
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
            "template_path": "./templates/template.user.docx",
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
            "next_step": "prepare",
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
