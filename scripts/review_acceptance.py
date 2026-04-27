from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts._preview_pairing import file_fingerprint, normalize_repo_relative
from scripts._shared import dump_json, emit_json, load_json, project_path
from scripts._task_contract import load_task_contract
from scripts._workflow_adapters import validate_review_result


WORKER_OUTPUT = "./out/_internal/review-worker-output.json"
REVIEW_PACKET = "./out/_internal/review-packet.json"
ACCEPTANCE_REVIEW = "./out/acceptance-review.json"


def build_review_packet(project_root: Path, task_contract: dict[str, Any]) -> dict[str, Any]:
    redacted_path = project_path(project_root, "out/redacted.docx")
    summary_path = project_path(project_root, "out/preview.summary.json")
    semantic_path = project_path(project_root, "out/semantic-preview.docx")
    packet = {
        "version": "1.0",
        "target": "./out/redacted.docx",
        "target_fingerprint": file_fingerprint(redacted_path),
        "verify": {
            "status": task_contract.get("runtime", {}).get("redacted_verify_status", "unknown"),
            "fingerprint": task_contract.get("runtime", {}).get("redacted_verify_fingerprint", ""),
            "artifact": task_contract.get("runtime", {}).get("redacted_verify", ""),
        },
        "preview": {
            "summary": "./out/preview.summary.json" if summary_path.exists() else "",
            "semantic_preview": "./out/semantic-preview.docx" if semantic_path.exists() else "",
            "preview_review_status": task_contract.get("runtime", {}).get("preview_review_status", "unknown"),
        },
        "requirements": {
            "task_requirements_path": "./docs/task_requirements.md",
            "document_requirements_path": "./docs/document_requirements.md",
            "report_body_path": "./docs/report_body.md",
        },
        "retry_context": task_contract.get("runtime", {}).get("retry_exhaustion", {}),
    }
    dump_json(project_path(project_root, REVIEW_PACKET.replace("./", "")), packet)
    return packet


def load_worker_output(project_root: Path) -> dict[str, Any] | None:
    output_path = project_path(project_root, WORKER_OUTPUT.replace("./", ""))
    if not output_path.exists():
        return None
    payload = load_json(output_path)
    if not isinstance(payload, dict):
        return None
    return payload


def validate_worker_output(packet: dict[str, Any], worker_output: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    status = worker_output.get("status")
    if status not in {
        "pass",
        "needs_rerender",
        "needs_rerender_redacted",
        "needs_rerender_semantic_preview",
        "needs_user_decision",
    }:
        errors.append("worker output missing valid status")
    target_fingerprint = worker_output.get("target_fingerprint")
    if not target_fingerprint:
        errors.append("worker output missing target fingerprint")
    elif target_fingerprint != packet["target_fingerprint"]:
        errors.append("worker output target fingerprint does not match current redacted artifact")
    return errors


def review_decision(worker_output: dict[str, Any]) -> str:
    status = str(worker_output.get("status", ""))
    if status in {
        "pass",
        "needs_rerender_redacted",
        "needs_rerender_semantic_preview",
        "needs_user_decision",
    }:
        return status
    if status != "needs_rerender":
        return status
    rerender_target = str(worker_output.get("rerender_target", ""))
    if rerender_target in {"semantic_preview", "drafting_inputs"}:
        return "needs_rerender_semantic_preview"
    return "needs_rerender_redacted"


def main() -> int:
    parser = argparse.ArgumentParser(description="Apply acceptance review decisions for the current redacted artifact.")
    parser.add_argument("--project-root", default=".")
    args = parser.parse_args()

    project_root = Path(args.project_root).resolve()
    task_contract = load_task_contract(project_root / "report.task.yaml")
    packet = build_review_packet(project_root, task_contract)
    worker_output = load_worker_output(project_root)
    if worker_output is None:
        emit_json(
            {
                "status": "error",
                "kind": "review_runtime_unavailable",
                "details": "missing acceptance-review worker output",
                "review_packet": REVIEW_PACKET,
                "worker_output": WORKER_OUTPUT,
            }
        )
        return 2

    errors = validate_worker_output(packet, worker_output)
    if errors:
        emit_json(
            {
                "status": "error",
                "kind": "invalid_review_worker_output",
                "details": errors,
                "review_packet": REVIEW_PACKET,
                "worker_output": WORKER_OUTPUT,
            }
        )
        return 2

    acceptance_payload = {
        "schema_version": "1.0",
        "step_name": "acceptance_review",
        "status": "ok",
        "decision": review_decision(worker_output),
        "target_artifact": packet["target"],
        "target_fingerprint": packet["target_fingerprint"],
        "blocking_findings": worker_output.get("blocking_findings", []),
        "needs_decision": worker_output.get("needs_decision", []),
        "evidence": worker_output.get("evidence", []),
        "recommended_next_step": worker_output.get("rerender_target", "review"),
    }
    acceptance_errors = validate_review_result(
        acceptance_payload,
        expected_step="acceptance_review",
        expected_fingerprint=str(packet["target_fingerprint"]),
    )
    if acceptance_errors:
        emit_json(
            {
                "status": "error",
                "kind": "invalid_acceptance_review_payload",
                "details": acceptance_errors,
                "review_packet": REVIEW_PACKET,
                "worker_output": WORKER_OUTPUT,
            }
        )
        return 2

    acceptance_path = project_path(project_root, ACCEPTANCE_REVIEW.replace("./", ""))
    dump_json(acceptance_path, acceptance_payload)
    emit_json(
        {
            "status": acceptance_payload["decision"],
            "decision": acceptance_payload["decision"],
            "acceptance_review": normalize_repo_relative(ACCEPTANCE_REVIEW),
            "review_packet": REVIEW_PACKET,
            "worker_output": WORKER_OUTPUT,
            "target_fingerprint": acceptance_payload["target_fingerprint"],
            "recommended_next_step": acceptance_payload["recommended_next_step"],
            "rerender_target": worker_output.get("rerender_target", "none"),
            "blocking_findings": acceptance_payload["blocking_findings"],
            "needs_decision": acceptance_payload["needs_decision"],
            "retry_exhaustion": worker_output.get("retry_exhaustion", {"status": "clear"}),
            "handoff_status": worker_output.get("handoff_status", ""),
        }
    )
    if acceptance_payload["decision"] == "pass":
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
