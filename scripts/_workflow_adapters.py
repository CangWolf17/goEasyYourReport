from __future__ import annotations


def validate_review_result(
    payload: dict[str, object],
    *,
    expected_step: str,
    expected_fingerprint: str,
) -> list[str]:
    errors: list[str] = []
    if payload.get("schema_version") != "1.0":
        errors.append("schema_version mismatch")
    if payload.get("step_name") != expected_step:
        errors.append("step_name mismatch")
    if payload.get("target_fingerprint") != expected_fingerprint:
        errors.append("target_fingerprint mismatch")
    if payload.get("decision") not in {
        "pass",
        "needs_rerender_redacted",
        "needs_rerender_semantic_preview",
        "needs_user_decision",
    }:
        errors.append("invalid decision")
    if not isinstance(payload.get("blocking_findings"), list):
        errors.append("blocking_findings must be a list")
    if not isinstance(payload.get("needs_decision"), list):
        errors.append("needs_decision must be a list")
    if not isinstance(payload.get("evidence"), list):
        errors.append("evidence must be a list")
    if not isinstance(payload.get("recommended_next_step"), str):
        errors.append("recommended_next_step must be a string")
    return errors
