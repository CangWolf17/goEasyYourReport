from __future__ import annotations

from copy import deepcopy


INVALIDATION_RULES = {
    "semantic_preview_basis": {"preview_review", "ready_gate"},
    "redacted_output": {"verify_redacted", "acceptance_review", "inject_private"},
}


def invalidate_approvals_for_artifact_change(
    runtime: dict[str, object],
    *,
    artifact_key: str,
    old_fingerprint: str,
    new_fingerprint: str,
) -> dict[str, object]:
    updated = deepcopy(runtime)
    if old_fingerprint == new_fingerprint:
        return updated

    approvals = dict(updated.get("approvals", {}))
    for key in INVALIDATION_RULES.get(artifact_key, set()):
        approvals.pop(key, None)
    updated["approvals"] = approvals

    if artifact_key == "semantic_preview_basis":
        updated["clear_ready_to_write"] = True

    return updated
