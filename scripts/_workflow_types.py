from __future__ import annotations

from typing import Final

STEP_RESULTS: Final[frozenset[str]] = frozenset(
    {
        "pass",
        "needs_user_decision",
        "needs_agent_revision",
        "needs_rerender",
        "needs_reverify",
        "needs_recritic",
        "artifact_stale",
        "process_contract_broken",
        "runtime_unavailable",
    }
)

TERMINAL_TASK_STATUS: Final[frozenset[str]] = frozenset({"complete", "failed"})
