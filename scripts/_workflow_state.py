from __future__ import annotations


def default_runtime_state() -> dict[str, object]:
    return {
        "current_step": "prepare",
        "next_step": "prepare",
        "last_result": "",
        "active_blockers": [],
        "artifacts": {},
        "approvals": {},
        "retries": {},
        "handoff": {},
    }
