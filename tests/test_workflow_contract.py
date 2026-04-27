import unittest

from scripts._workflow_blockers import make_blocker
from scripts._workflow_state import default_runtime_state
from scripts._workflow_types import STEP_RESULTS, TERMINAL_TASK_STATUS


class WorkflowContractTests(unittest.TestCase):
    def test_default_runtime_state_seeds_phase2_control_plane_fields(self) -> None:
        runtime = default_runtime_state()
        self.assertEqual(
            runtime,
            {
                "current_step": "prepare",
                "next_step": "prepare",
                "last_result": "",
                "active_blockers": [],
                "artifacts": {},
                "approvals": {},
                "retries": {},
                "handoff": {},
            },
        )

    def test_make_blocker_normalizes_required_fields(self) -> None:
        blocker = make_blocker(
            "artifact_stale",
            owner="framework",
            step="ready_gate",
            details="preview no longer matches current inputs",
            recommended_next_step="preview",
            auto_resolvable=True,
        )
        self.assertEqual(
            blocker,
            {
                "kind": "artifact_stale",
                "owner": "framework",
                "step": "ready_gate",
                "target_artifact": "",
                "target_fingerprint": "",
                "details": "preview no longer matches current inputs",
                "recommended_next_step": "preview",
                "auto_resolvable": True,
            },
        )

    def test_control_plane_constants_cover_expected_states(self) -> None:
        self.assertIsInstance(STEP_RESULTS, frozenset)
        self.assertEqual(
            STEP_RESULTS,
            frozenset(
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
            ),
        )
        self.assertIsInstance(TERMINAL_TASK_STATUS, frozenset)
        self.assertEqual(
            TERMINAL_TASK_STATUS,
            frozenset({"complete", "failed"}),
        )
