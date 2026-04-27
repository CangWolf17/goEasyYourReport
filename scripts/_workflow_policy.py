from __future__ import annotations

from pathlib import Path
from typing import Any

from scripts._semantic_preview import semantic_preview_basis
from scripts._preview_pairing import file_fingerprint
from scripts._shared import project_path


def current_fingerprint(project_root: Path, relative_path: str) -> str | None:
    path = project_path(project_root, relative_path.replace("./", ""))
    if not path.exists():
        return None
    return file_fingerprint(path)


def compute_preview_review(
    project_root: Path,
    task_contract: dict[str, Any],
    summary_payload: dict[str, Any],
    pair_state_payload: dict[str, Any],
    *,
    verify_ok: bool = True,
) -> dict[str, Any]:
    runtime = task_contract.get("runtime", {})
    semantic_preview = summary_payload.get("semantic_preview", {})
    semantic_path = semantic_preview.get(
        "path", runtime.get("semantic_preview_output", "./out/semantic-preview.docx")
    )
    semantic_docx = project_path(project_root, str(semantic_path).replace("./", ""))
    blocking = summary_payload.get("review", {}).get("blocking", [])
    decisions = summary_payload.get("review", {}).get("decision_required", [])

    if not semantic_docx.exists():
        status = "needs_preview_revision"
        cause = "missing_semantic_preview"
        next_step = "preview"
    elif not verify_ok:
        status = "needs_preview_revision"
        cause = "semantic_or_contract_preview_not_verified"
        next_step = "preview"
    elif pair_state_payload.get("pair_state") != "matched":
        status = "needs_preview_revision"
        cause = f"pair_state:{pair_state_payload.get('pair_state')}"
        next_step = "preview"
    elif blocking or decisions:
        status = "needs_user_decision"
        cause = "preview_review_items_pending"
        next_step = "review_preview_summary"
    else:
        status = "pass"
        cause = "preview_ready"
        next_step = "build"

    return {
        "path": semantic_path,
        "status": status,
        "cause": cause,
        "next_step": next_step,
        "freshness_basis": {
            "pair_state": pair_state_payload.get("pair_state"),
            "source_path": semantic_preview.get("source_path", "./docs/report_body.md"),
            "source_fingerprint": semantic_preview.get("source_fingerprint", ""),
            "render_input_path": semantic_preview.get("render_input_path", "./docs/report_body.md"),
            "render_input_fingerprint": semantic_preview.get("render_input_fingerprint", ""),
            "scaffold_mode": semantic_preview.get("scaffold_mode", "unknown"),
        },
    }


def build_precondition_issues(
    project_root: Path,
    task_contract: dict[str, Any],
    summary_payload: dict[str, Any],
    pair_state_payload: dict[str, Any],
) -> list[dict[str, str]]:
    runtime = task_contract.get("runtime", {})
    issues: list[dict[str, str]] = []

    if runtime.get("preview_review_status") != "pass":
        issues.append(
            {
                "kind": "preview_review_not_passed",
                "details": "preview must pass review before build",
            }
        )

    if pair_state_payload.get("pair_state") != "matched":
        issues.append(
            {
                "kind": "stale_preview_pair",
                "details": "preview/recommendation pairing is no longer current",
            }
        )

    semantic_path = runtime.get("semantic_preview_output", "./out/semantic-preview.docx")
    semantic_docx = project_path(project_root, str(semantic_path).replace("./", ""))
    if not semantic_docx.exists():
        issues.append(
            {
                "kind": "missing_semantic_preview",
                "details": "semantic preview artifact must exist before build",
            }
        )

    semantic_preview = summary_payload.get("semantic_preview", {})
    stored_source_fingerprint = str(
        semantic_preview.get("source_fingerprint")
        or runtime.get("preview_review_basis", {}).get("source_fingerprint", "")
    )
    stored_render_input_fingerprint = str(
        semantic_preview.get("render_input_fingerprint")
        or runtime.get("preview_review_basis", {}).get("render_input_fingerprint", "")
    )
    stored_scaffold_mode = str(
        semantic_preview.get("scaffold_mode")
        or runtime.get("preview_review_basis", {}).get("scaffold_mode", "")
    )
    current_basis = semantic_preview_basis(project_root)
    if (
        stored_source_fingerprint != str(current_basis["source_fingerprint"])
        or stored_render_input_fingerprint
        != str(current_basis["render_input_fingerprint"])
        or stored_scaffold_mode != str(current_basis["scaffold_mode"])
    ):
        issues.append(
            {
                "kind": "stale_semantic_preview",
                "details": "preview-driving inputs changed after the approved preview",
            }
        )

    return issues


def review_precondition_issues(
    task_contract: dict[str, Any],
    current_redacted_fingerprint: str | None,
) -> list[dict[str, str]]:
    runtime = task_contract.get("runtime", {})
    issues: list[dict[str, str]] = []
    if not runtime.get("redacted_output"):
        issues.append({"kind": "missing_redacted_output", "details": "build must run before review"})
    if runtime.get("redacted_verify_status") != "pass":
        issues.append({"kind": "missing_redacted_verify_pass", "details": "verify --target redacted must pass before review"})
    verify_fingerprint = runtime.get("redacted_verify_fingerprint")
    if not verify_fingerprint or verify_fingerprint != current_redacted_fingerprint:
        issues.append({"kind": "stale_redacted_verify", "details": "current redacted fingerprint does not match verified artifact"})
    return issues


def inject_precondition_issues(
    task_contract: dict[str, Any],
    current_redacted_fingerprint: str | None,
) -> list[dict[str, str]]:
    runtime = task_contract.get("runtime", {})
    issues: list[dict[str, str]] = []
    if runtime.get("acceptance_status") != "pass":
        issues.append({"kind": "acceptance_not_passed", "details": "review must pass before inject"})
    accepted_fingerprint = runtime.get("accepted_redacted_fingerprint")
    if not accepted_fingerprint:
        issues.append({"kind": "missing_accepted_redacted_fingerprint", "details": "accepted redacted fingerprint is missing"})
    elif accepted_fingerprint != current_redacted_fingerprint:
        issues.append({"kind": "stale_accepted_redacted_fingerprint", "details": "accepted fingerprint does not match current redacted output"})
    return issues


def rerender_target_next_step(rerender_target: str, status: str) -> str:
    if status == "needs_user_decision":
        return "review"
    mapping = {
        "semantic_preview": "preview",
        "drafting_inputs": "preview",
        "section_refinement": "build",
        "build_redacted": "build",
        "none": "review",
    }
    return mapping.get(rerender_target, "review")
