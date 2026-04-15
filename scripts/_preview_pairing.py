from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any
from uuid import uuid4
from datetime import datetime, timezone

from scripts._shared import load_json, project_path


PAIR_ISSUE_PRECEDENCE = (
    "missing_pairing_metadata",
    "mismatched_preview_pair",
    "stale_preview_pair",
)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')


def normalize_repo_relative(path_text: str) -> str:
    normalized = Path(path_text).as_posix()
    if normalized.startswith("./"):
        return normalized
    return f"./{normalized.lstrip('./')}"


def file_fingerprint(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def _normalized_payload(payload: dict[str, Any]) -> dict[str, Any]:
    result = dict(payload)
    result.pop("pairing", None)
    return result


def recommendation_fingerprint(payload: dict[str, Any] | None) -> str | None:
    if not payload:
        return None
    normalized = json.dumps(_normalized_payload(payload), ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def build_pairing(
    project_root: Path,
    *,
    template_path: str,
    template_fingerprint: str,
    recommendation_fingerprint_value: str | None,
    recommended_template_path: str | None,
    preview_path: str,
    preview_summary_path: str,
    recommendation_path: str,
    pair_id: str | None = None,
    generated_at: str | None = None,
) -> dict[str, str | None]:
    return {
        "pair_id": pair_id or str(uuid4()),
        "template_path": template_path,
        "template_fingerprint": template_fingerprint,
        "recommendation_fingerprint": recommendation_fingerprint_value,
        "recommended_template_path": recommended_template_path,
        "generated_at": generated_at or utc_now_iso(),
        "preview_path": preview_path,
        "preview_summary_path": preview_summary_path,
        "recommendation_path": recommendation_path,
    }


def canonical_issue_kind(issue_kinds: list[str]) -> str | None:
    if not issue_kinds:
        return None
    for kind in PAIR_ISSUE_PRECEDENCE:
        if kind in issue_kinds:
            return kind
    return issue_kinds[0]


def evaluate_preview_pair_state(
    project_root: Path,
    *,
    recommendation_payload: dict[str, Any] | None,
    preview_summary: dict[str, Any] | None,
) -> dict[str, Any]:
    recommendation_pairing = None
    if isinstance(recommendation_payload, dict):
        recommendation_pairing = recommendation_payload.get("pairing")
    summary_pairing = None
    if isinstance(preview_summary, dict):
        summary_pairing = preview_summary.get("pairing")

    if not isinstance(recommendation_payload, dict):
        return {"pair_state": "missing", "issue_kinds": ["missing_template_recommendation"], "next_step": "preview", "pairing": None}
    if not isinstance(preview_summary, dict):
        return {"pair_state": "missing", "issue_kinds": ["missing_preview_summary"], "next_step": "preview", "pairing": None}
    if not isinstance(recommendation_pairing, dict) or not isinstance(summary_pairing, dict):
        return {"pair_state": "missing", "issue_kinds": ["missing_pairing_metadata"], "next_step": "preview", "pairing": summary_pairing or recommendation_pairing}

    required_fields = (
        "pair_id",
        "template_path",
        "template_fingerprint",
        "recommendation_fingerprint",
        "recommended_template_path",
    )
    if any(not recommendation_pairing.get(field) or not summary_pairing.get(field) for field in required_fields):
        return {"pair_state": "missing", "issue_kinds": ["missing_pairing_metadata"], "next_step": "preview", "pairing": summary_pairing}

    mismatch_fields = [
        field for field in required_fields if recommendation_pairing.get(field) != summary_pairing.get(field)
    ]
    if mismatch_fields:
        return {"pair_state": "mismatched", "issue_kinds": ["mismatched_preview_pair"], "next_step": "preview", "pairing": summary_pairing, "mismatch_fields": mismatch_fields}

    plan_path = project_path(project_root, "config/template.plan.json")
    current_template_path_value = str(summary_pairing["template_path"])
    if plan_path.exists():
        plan = load_json(plan_path)
        selection = plan.get("selection", {})
        if isinstance(selection, dict) and selection.get("primary_template"):
            current_template_path_value = str(selection["primary_template"])
    current_template_path = project_path(project_root, current_template_path_value.replace("./", ""))
    current_template_fingerprint = file_fingerprint(current_template_path) if current_template_path.exists() else None
    current_recommendation_fingerprint = recommendation_fingerprint(recommendation_payload)
    stale = (
        current_template_path_value != summary_pairing.get("template_path")
        or current_template_path_value != recommendation_pairing.get("template_path")
        or current_template_fingerprint != summary_pairing.get("template_fingerprint")
        or current_recommendation_fingerprint != summary_pairing.get("recommendation_fingerprint")
    )
    if stale:
        return {"pair_state": "stale", "issue_kinds": ["stale_preview_pair"], "next_step": "preview", "pairing": summary_pairing}

    return {"pair_state": "matched", "issue_kinds": [], "next_step": "review_preview_summary", "pairing": summary_pairing}
