import unittest
from unittest.mock import patch

from scripts._workflow_engine import advance_step
from scripts._workflow_artifacts import invalidate_approvals_for_artifact_change
from scripts._workflow_adapters import validate_review_result
from scripts._workflow_playbook import TRANSITIONS


class WorkflowArtifactTests(unittest.TestCase):
    def test_redacted_change_invalidates_only_targeted_approvals(self) -> None:
        runtime = {
            "approvals": {
                "verify_redacted": {"target_fingerprint": "old"},
                "acceptance_review": {"target_fingerprint": "old"},
                "inject_private": {"target_fingerprint": "old"},
                "preview_review": {"target_fingerprint": "keep"},
            }
        }
        changed = invalidate_approvals_for_artifact_change(
            runtime,
            artifact_key="redacted_output",
            old_fingerprint="old",
            new_fingerprint="new",
        )
        self.assertEqual(
            changed["approvals"],
            {"preview_review": {"target_fingerprint": "keep"}},
        )

    def test_preview_input_change_emits_ready_gate_reset_signal(self) -> None:
        runtime = {
            "approvals": {"preview_review": {"target_fingerprint": "preview-a"}},
            "ready_to_write": True,
        }
        changed = invalidate_approvals_for_artifact_change(
            runtime,
            artifact_key="semantic_preview_basis",
            old_fingerprint="basis-a",
            new_fingerprint="basis-b",
        )
        self.assertEqual(changed["approvals"], {})
        self.assertTrue(changed["ready_to_write"])
        self.assertTrue(changed["clear_ready_to_write"])

    def test_unchanged_fingerprints_are_a_no_op(self) -> None:
        runtime = {
            "approvals": {"preview_review": {"target_fingerprint": "preview-a"}},
            "ready_to_write": True,
        }
        changed = invalidate_approvals_for_artifact_change(
            runtime,
            artifact_key="semantic_preview_basis",
            old_fingerprint="basis-a",
            new_fingerprint="basis-a",
        )
        self.assertEqual(changed, runtime)


class WorkflowAdapterTests(unittest.TestCase):
    def test_validate_review_result_rejects_missing_target_fingerprint(self) -> None:
        errors = validate_review_result(
            {
                "schema_version": "1.0",
                "step_name": "acceptance_review",
                "status": "ok",
                "decision": "pass",
                "target_artifact": "./out/redacted.docx",
                "blocking_findings": [],
                "needs_decision": [],
                "evidence": [],
                "recommended_next_step": "inject",
            },
            expected_step="acceptance_review",
            expected_fingerprint="abc",
        )
        self.assertTrue(errors)

    def test_validate_review_result_rejects_malformed_collection_types(self) -> None:
        errors = validate_review_result(
            {
                "schema_version": "1.0",
                "step_name": "acceptance_review",
                "status": "ok",
                "decision": "pass",
                "target_artifact": "./out/redacted.docx",
                "target_fingerprint": "abc",
                "blocking_findings": "not-a-list",
                "needs_decision": [],
                "evidence": [],
                "recommended_next_step": "inject",
            },
            expected_step="acceptance_review",
            expected_fingerprint="abc",
        )
        self.assertIn("blocking_findings must be a list", errors)

    def test_validate_review_result_accepts_matching_payload(self) -> None:
        errors = validate_review_result(
            {
                "schema_version": "1.0",
                "step_name": "acceptance_review",
                "status": "ok",
                "decision": "pass",
                "target_artifact": "./out/redacted.docx",
                "target_fingerprint": "abc",
                "blocking_findings": [],
                "needs_decision": [],
                "evidence": [],
                "recommended_next_step": "inject",
            },
            expected_step="acceptance_review",
            expected_fingerprint="abc",
        )
        self.assertEqual(errors, [])


class WorkflowTransitionTests(unittest.TestCase):
    def test_transition_key_set_matches_phase2_matrix(self) -> None:
        expected_keys = {
            ("prepare", "pass"),
            ("prepare", "process_contract_broken"),
            ("preview", "pass"),
            ("preview", "needs_user_decision"),
            ("preview", "artifact_stale"),
            ("preview_review", "pass"),
            ("preview_review", "needs_user_decision"),
            ("preview_review", "needs_rerender_semantic_preview"),
            ("ready_gate", "pass"),
            ("ready_gate", "artifact_stale"),
            ("build_redacted", "pass"),
            ("build_redacted", "needs_agent_revision"),
            ("verify_redacted", "pass"),
            ("verify_redacted", "needs_agent_revision"),
            ("verify_redacted", "needs_reverify"),
            ("acceptance_review", "pass"),
            ("acceptance_review", "needs_user_decision"),
            ("acceptance_review", "needs_rerender_redacted"),
            ("acceptance_review", "needs_rerender_semantic_preview"),
            ("inject_private", "pass"),
            ("inject_private", "process_contract_broken"),
            ("post_inject_check", "pass"),
            ("post_inject_check", "needs_agent_revision"),
        }
        self.assertEqual(set(TRANSITIONS), expected_keys)

    def test_all_transition_rows_advance_as_declared(self) -> None:
        for (current_step, result), (expected_next_step, side_effects) in TRANSITIONS.items():
            with self.subTest(current_step=current_step, result=result):
                runtime = {"current_step": current_step, "next_step": current_step}
                updated = advance_step(runtime, result=result)
                self.assertEqual(updated["current_step"], expected_next_step)
                self.assertEqual(updated["next_step"], expected_next_step)
                self.assertEqual(updated["last_result"], result)
                for key, value in side_effects.items():
                    self.assertEqual(updated[key], value)

    def test_preview_review_pass_advances_to_ready_gate(self) -> None:
        runtime = {"current_step": "preview_review", "next_step": "preview_review"}
        updated = advance_step(runtime, result="pass")
        self.assertEqual(updated["current_step"], "ready_gate")
        self.assertEqual(updated["next_step"], "ready_gate")

    def test_acceptance_rerender_redacted_returns_to_build(self) -> None:
        runtime = {
            "current_step": "acceptance_review",
            "next_step": "acceptance_review",
        }
        updated = advance_step(runtime, result="needs_rerender_redacted")
        self.assertEqual(updated["next_step"], "build_redacted")

    def test_ready_gate_artifact_stale_clears_ready_to_write(self) -> None:
        runtime = {
            "current_step": "ready_gate",
            "next_step": "ready_gate",
            "ready_to_write": True,
        }
        updated = advance_step(runtime, result="artifact_stale")
        self.assertFalse(updated["ready_to_write"])
        self.assertEqual(updated["next_step"], "preview")

    def test_last_result_is_always_written(self) -> None:
        for (current_step, result) in TRANSITIONS:
            with self.subTest(current_step=current_step, result=result):
                updated = advance_step(
                    {"current_step": current_step, "next_step": current_step},
                    result=result,
                )
                self.assertEqual(updated["last_result"], result)

    def test_advance_step_does_not_mutate_input_runtime(self) -> None:
        runtime = {
            "current_step": "ready_gate",
            "next_step": "ready_gate",
            "ready_to_write": True,
        }
        snapshot = dict(runtime)
        updated = advance_step(runtime, result="artifact_stale")
        self.assertEqual(runtime, snapshot)
        self.assertIsNot(updated, runtime)

    def test_non_string_or_empty_current_step_is_rejected(self) -> None:
        for invalid_step in (None, "", 123):
            with self.subTest(current_step=invalid_step):
                with self.assertRaises(ValueError):
                    advance_step({"current_step": invalid_step, "next_step": "preview"}, result="pass")

    def test_unknown_transition_raises_value_error_with_context(self) -> None:
        with self.assertRaisesRegex(
            ValueError,
            "unknown transition.*preview_review.*artifact_stale",
        ):
            advance_step(
                {"current_step": "preview_review", "next_step": "preview_review"},
                result="artifact_stale",
            )

    def test_reserved_engine_keys_in_side_effects_raise_value_error(self) -> None:
        with patch.dict(
            TRANSITIONS,
            {
                ("prepare", "pass"): (
                    "preview",
                    {
                        "current_step": "corrupt",
                        "next_step": "corrupt",
                        "last_result": "corrupt",
                        "ready_to_write": True,
                    },
                )
            },
            clear=False,
        ):
            with self.assertRaises(ValueError) as error_context:
                advance_step(
                    {"current_step": "prepare", "next_step": "prepare"},
                    result="pass",
                )
        message = str(error_context.exception)
        self.assertIn("side_effects must not override reserved runtime keys", message)
        self.assertIn("current_step", message)
        self.assertIn("next_step", message)
        self.assertIn("last_result", message)

    def test_completion_transition_does_not_inject_task_status(self) -> None:
        updated = advance_step(
            {"current_step": "post_inject_check", "next_step": "post_inject_check"},
            result="pass",
        )
        self.assertEqual(updated["current_step"], "complete")
        self.assertNotIn("task_status", updated)
