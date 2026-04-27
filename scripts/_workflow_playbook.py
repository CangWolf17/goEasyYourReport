from __future__ import annotations

TRANSITIONS = {
    ("prepare", "pass"): ("preview", {}),
    ("prepare", "process_contract_broken"): ("repair_runtime", {}),
    ("preview", "pass"): ("preview_review", {}),
    ("preview", "needs_user_decision"): ("preview_review", {}),
    ("preview", "artifact_stale"): ("preview", {}),
    ("preview_review", "pass"): ("ready_gate", {}),
    ("preview_review", "needs_user_decision"): ("preview_review", {}),
    ("preview_review", "needs_rerender_semantic_preview"): (
        "preview",
        {"ready_to_write": False},
    ),
    ("ready_gate", "pass"): ("build_redacted", {"ready_to_write": True}),
    ("ready_gate", "artifact_stale"): ("preview", {"ready_to_write": False}),
    ("build_redacted", "pass"): ("verify_redacted", {}),
    ("build_redacted", "needs_agent_revision"): ("build_redacted", {}),
    ("verify_redacted", "pass"): ("acceptance_review", {}),
    ("verify_redacted", "needs_agent_revision"): ("build_redacted", {}),
    ("verify_redacted", "needs_reverify"): ("verify_redacted", {}),
    ("acceptance_review", "pass"): ("inject_private", {}),
    ("acceptance_review", "needs_user_decision"): ("acceptance_review", {}),
    ("acceptance_review", "needs_rerender_redacted"): ("build_redacted", {}),
    ("acceptance_review", "needs_rerender_semantic_preview"): (
        "preview",
        {"ready_to_write": False},
    ),
    ("inject_private", "pass"): ("post_inject_check", {}),
    ("inject_private", "process_contract_broken"): ("repair_runtime", {}),
    ("post_inject_check", "pass"): ("complete", {}),
    ("post_inject_check", "needs_agent_revision"): ("inject_private", {}),
}
