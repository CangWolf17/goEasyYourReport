from __future__ import annotations


def make_blocker(
    kind: str,
    *,
    owner: str,
    step: str,
    details: str,
    recommended_next_step: str,
    auto_resolvable: bool,
    target_artifact: str = "",
    target_fingerprint: str = "",
) -> dict[str, object]:
    return {
        "kind": kind,
        "owner": owner,
        "step": step,
        "target_artifact": target_artifact,
        "target_fingerprint": target_fingerprint,
        "details": details,
        "recommended_next_step": recommended_next_step,
        "auto_resolvable": auto_resolvable,
    }
