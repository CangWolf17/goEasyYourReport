from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from scripts._shared import PROJECT_ROOT, dump_json, load_json

DEFAULT_DECISIONS = {
    "report_profile": "standard",
    "toc_enabled": None,
    "references_required": None,
    "appendix_enabled": None,
    "agent_may_write_explanatory_text": True,
    "default_template_protected": True,
}


def global_defaults_path() -> Path:
    override = os.environ.get("GOEASY_GLOBAL_DEFAULTS_PATH")
    if override:
        return Path(override).resolve()
    codex_home = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex"))
    return (codex_home / "skills" / "go-easy-your-report" / "global-defaults.json").resolve()


def default_global_defaults() -> dict[str, object]:
    return {
        "version": "1.0",
        "templates": {
            "template_source": str((PROJECT_ROOT / "templates" / "template.sample.docx").resolve()),
            "reference_template_source": str((PROJECT_ROOT / "templates" / "reference.sample.docx").resolve()),
        },
        "decisions": dict(DEFAULT_DECISIONS),
    }


def load_global_defaults(path: Path | None = None) -> dict[str, object] | None:
    target = path or global_defaults_path()
    if not target.exists():
        return None
    payload = load_json(target)
    if not isinstance(payload, dict):
        return None
    return payload


def save_global_defaults(payload: dict[str, Any], path: Path | None = None) -> Path:
    target = path or global_defaults_path()
    dump_json(target, payload)
    return target


def export_global_defaults(target: Path) -> Path:
    payload = load_global_defaults()
    if payload is None:
        raise SystemExit("Global defaults not found")
    dump_json(target, payload)
    return target


def import_global_defaults(source: Path) -> Path:
    if not source.exists():
        raise SystemExit(f"Global defaults source not found: {source}")
    payload = load_json(source)
    if not isinstance(payload, dict):
        raise SystemExit("Global defaults source must be a JSON object")
    return save_global_defaults(payload)


def apply_global_defaults_to_task_contract(
    task_contract: dict[str, object],
    defaults: dict[str, object] | None,
    *,
    overwrite_existing: bool = False,
) -> bool:
    if not defaults:
        return False
    decisions = task_contract.setdefault("decisions", {})
    if not isinstance(decisions, dict):
        return False
    changed = False
    default_decisions = defaults.get("decisions", {})
    if not isinstance(default_decisions, dict):
        return False
    for key, value in default_decisions.items():
        if overwrite_existing or decisions.get(key) is None:
            decisions[key] = value
            changed = True
    return changed


def _copy_if_missing(source_path: str | None, destination: Path) -> bool:
    if not source_path:
        return False
    source = Path(source_path).resolve()
    if not source.exists() or destination.exists():
        return False
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(source.read_bytes())
    return True


def seed_missing_project_defaults(
    project_root: Path,
    task_contract: dict[str, object] | None = None,
    *,
    overwrite_decisions: bool = False,
) -> bool:
    defaults = load_global_defaults()
    if not defaults:
        return False
    changed = False
    templates = defaults.get("templates", {})
    if isinstance(templates, dict):
        changed = _copy_if_missing(
            str(templates.get("template_source") or ""),
            project_root / "templates" / "template.user.docx",
        ) or changed
        changed = _copy_if_missing(
            str(templates.get("reference_template_source") or ""),
            project_root / "templates" / "reference.user.docx",
        ) or changed
    if task_contract is not None:
        changed = (
            apply_global_defaults_to_task_contract(
                task_contract,
                defaults,
                overwrite_existing=overwrite_decisions,
            )
            or changed
        )
    return changed
